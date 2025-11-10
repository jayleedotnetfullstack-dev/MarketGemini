// src/app/services/series.service.ts
import { Injectable, Inject, PLATFORM_ID } from '@angular/core';
import { isPlatformBrowser } from '@angular/common';
import {
  HttpClient,
  HttpHeaders,
  HttpParams,
  HttpErrorResponse,
} from '@angular/common/http';
import { environment } from '../../environments/environment';
import { Observable, throwError } from 'rxjs';
import { tap, catchError, timeout, retry, finalize } from 'rxjs/operators';

export interface SeriesPoint { t: string | number; v: number; }
export interface SeriesResponse {
  asset: string;
  series: [string | number, number][];
  meta?: any;
  indicators?: Record<string, number[]>;
  anomalies?: boolean[];
}
export interface AnomalyResponse { scores: number[]; anomalies: boolean[]; }

@Injectable({ providedIn: 'root' })
export class SeriesService {
  // ✅ Base API URL selection: localStorage > environment > localhost
private base = (() => {
  try {
    const ls = typeof window !== 'undefined' ? window.localStorage : null;
    const fromLS = ls?.getItem('mg_api');

    // Priority:
    // 1. User override via localStorage.mg_api
    // 2. environment.apiBaseUrl
    // 3. fallback = http://localhost:8000
    return (fromLS && fromLS.trim())
      ? fromLS.trim()
      : ((environment as any)?.apiBaseUrl?.toString?.() || 'http://localhost:8000');
  } catch {
    return (environment as any)?.apiBaseUrl?.toString?.() || 'http://localhost:8000';
  }
})();

  // ✅ component can render this when a call fails
  public lastErrorMessage = '';

  constructor(
    private http: HttpClient,
    @Inject(PLATFORM_ID) private platformId: Object
  ) {}

  private isBrowser(): boolean { return isPlatformBrowser(this.platformId); }

  private get debug(): boolean {
    if (!this.isBrowser()) return false;
    try { return (localStorage.getItem('mg_debug') || '') === '1'; } catch { return false; }
  }

  setToken(token: string) {
    if (!this.isBrowser()) return;
    try {
      localStorage.setItem('mg_token', token || '');
      if (this.debug) console.info('[SeriesService] Token saved (masked).');
    } catch { /* no-op */ }
  }
  clearToken() {
    if (!this.isBrowser()) return;
    try {
      localStorage.removeItem('mg_token');
      if (this.debug) console.info('[SeriesService] Token cleared.');
    } catch { /* no-op */ }
  }
  private readToken(): string {
    if (!this.isBrowser()) return '';
    try { return localStorage.getItem('mg_token') || ''; } catch { return ''; }
  }
  private maskToken(tok: string, keep = 12): string {
    if (!tok) return '<none>'; return tok.slice(0, keep) + '…(masked)…';
  }
  private authHeaders(): HttpHeaders {
    const token = this.readToken();
    const headers = token ? { Authorization: `Bearer ${token}` } : undefined;
    if (this.debug) {
      console.debug('[SeriesService] authHeaders', { hasToken: !!token, tokenMasked: this.maskToken(token) });
    }
    return new HttpHeaders(headers || {});
  }

  // ----- API calls -----
  getSeries(asset: string, includeIndicators?: string | string[]): Observable<SeriesResponse> {
    let params = new HttpParams().set('asset', asset);
    if (Array.isArray(includeIndicators) && includeIndicators.length > 0) {
      params = params.set('include_indicators', includeIndicators.join(','));
    } else if (typeof includeIndicators === 'string' && includeIndicators.trim()) {
      params = params.set('include_indicators', includeIndicators.trim());
    }

    const url = `${this.base}/v1/series`;
    if (this.debug) {
      console.log('[SeriesService] GET', url, {
        params: Object.fromEntries((params as any).keys().map((k: string) => [k, params.get(k)])),
      });
    }

    return this.http.get<SeriesResponse>(url, { headers: this.authHeaders(), params })
      .pipe(
        timeout(10000),
        retry(1),
        tap((res) => {
          if (this.debug) {
            console.log('[SeriesService] /v1/series OK', {
              asset: res?.asset, points: res?.series?.length ?? 0,
              hasIndicators: !!res?.indicators, hasAnomalies: !!res?.anomalies,
            });
          }
        }),
        catchError((err) => this.handleError(err, 'GET /v1/series')),
        finalize(() => { if (this.debug) console.debug('[SeriesService] GET /v1/series complete.'); }),
      );
  }

  getAnomalies(values: number[], window = 30, threshold = 3.5): Observable<AnomalyResponse> {
    const url = `${this.base}/v1/anomaly`;
    const body = { values, window, threshold };
    if (this.debug) console.log('[SeriesService] POST', url, { bodyPreview: { window, threshold, n: values?.length || 0 } });

    return this.http.post<AnomalyResponse>(url, body, { headers: this.authHeaders() })
      .pipe(
        timeout(10000),
        tap((res) => {
          if (this.debug) {
            console.log('[SeriesService] /v1/anomaly OK', {
              scores: res?.scores?.length ?? 0,
              anomalies: res?.anomalies?.filter(Boolean).length ?? 0,
            });
          }
        }),
        catchError((err) => this.handleError(err, 'POST /v1/anomaly')),
        finalize(() => { if (this.debug) console.debug('[SeriesService] POST /v1/anomaly complete.'); }),
      );
  }

  ping(): Observable<any> {
    const url = `${this.base}/healthz`;
    if (this.debug) console.log('[SeriesService] GET', url);
    return this.http.get(url).pipe(
      timeout(5000),
      tap(() => this.debug && console.log('[SeriesService] /healthz OK')),
      catchError((err) => this.handleError(err, 'GET /healthz')),
    );
  }

  printDiag() {
    console.info('[SeriesService] DIAG', {
      base: this.base,
      hasToken: !!this.readToken(),
      tokenMasked: this.maskToken(this.readToken()),
      debug: this.debug,
      runtime: this.isBrowser() ? 'browser' : 'server',
    });
  }

  // ----- errors -----
  private handleError(err: unknown, where: string) {
    // Build a short, user-facing message
    const buildMsg = (status?: number, statusText?: string, url?: string | null, body?: string) =>
      `${status ? 'HTTP ' + status + (statusText ? ' ' + statusText : '') : 'Error'} @ ${where}${url ? ' ' + url : ''}${body ? ' | ' + body : ''}`;

    if (err instanceof HttpErrorResponse) {
      const bodyTxt =
        typeof err.error === 'string' ? err.error.slice(0, 400)
        : JSON.stringify(err.error || {}, null, 2).slice(0, 400);

      console.error(`[SeriesService] ${where} ERROR`, {
        status: err.status, statusText: err.statusText, url: err.url, body: bodyTxt,
      });

      if (err.status === 401) {
        console.warn(
          '[SeriesService] 401 Unauthorized. Save an INTERNAL HS256 token (localStorage.mg_token) ' +
          'or use OIDC exchange. Check backend for issuer/audience/scope.'
        );
      }

      this.lastErrorMessage = buildMsg(err.status, err.statusText, err.url ?? null, bodyTxt);
    } else {
      console.error(`[SeriesService] ${where} ERROR (non-HTTP)`, err);
      this.lastErrorMessage = buildMsg(undefined, undefined, undefined, 'non-HTTP error (see console)');
    }
    return throwError(() => err);
  }
}
