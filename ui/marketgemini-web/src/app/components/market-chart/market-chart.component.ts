// src/app/components/market-chart/market-chart.component.ts
import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import type { EChartsOption } from 'echarts';
import { NgxEchartsDirective } from 'ngx-echarts';

import { SeriesService, SeriesResponse } from '../../services/series.service';

@Component({
  selector: 'app-market-chart',
  standalone: true,
  imports: [CommonModule, FormsModule, NgxEchartsDirective],
  templateUrl: './market-chart.component.html',
  styleUrls: ['./market-chart.component.scss'],
})
export class MarketChartComponent implements OnInit {
  asset = 'GOLD';
  loading = false;
  error = '';

  // ✅ Option A fix: keep a detailed error string for the <pre> block
  errorDetail = '';

  showSMA50 = true;
  showSMA200 = true;
  showAnomalies = true;

  chartOptions: EChartsOption = {};
  chartInit = false;

  constructor(private seriesSvc: SeriesService) {}

  ngOnInit(): void {
    this.seriesSvc.printDiag();
    // Optional: auto-load on first paint
    // this.load();
  }

  saveToken(tok: string): void {
    // Route through service so SSR never touches localStorage here
    this.seriesSvc.setToken(tok || '');
    console.info('[MarketChart] token saved (masked via service)');
  }

  load(): void {
    this.error = '';
    this.errorDetail = '';   // ✅ reset detail each load
    this.loading = true;

    // Build include_indicators based on toggles
    const want: string[] = [];
    if (this.showSMA50) want.push('sma_50');
    if (this.showSMA200) want.push('sma_200');

    console.time('[MarketChart] /v1/series');
    console.log('[MarketChart] load()', { asset: this.asset, want });

    this.seriesSvc.getSeries(this.asset, want).subscribe({
      next: (body: SeriesResponse) => {
        console.log('[MarketChart] /v1/series OK', {
          points: body?.series?.length ?? 0,
          hasIndicators: !!body?.indicators,
          hasAnomalies: !!body?.anomalies,
        });

        // ✅ Build options first
        const options = this.buildOptions(body);

        // ✅ Compute names once from options, then publish to both the legacy global and the test bridge
        try {
          if (typeof window !== 'undefined') {
            const names =
              (options?.series as any[] | undefined)?.map(s => s?.name).filter(Boolean) ?? [];
            (window as any).__mgSeriesNames = names;                  // legacy global for manual debugging
            (window as any).__reportSeries?.(names);                  // 🔔 notify Playwright bridge
            if (localStorage.getItem('mg_debug') === '1') {
              console.log('[MarketChart] debug hook (load) names:', names);
            }
          }
        } catch { /* no-op */ }

        // ✅ Now apply options to the chart
        this.chartOptions = options;
        this.chartInit = true;
      },
      error: (err) => {
        // Short message + detailed block (from service if available)
        this.error = (this.seriesSvc as any).lastErrorMessage || this.formatError(err);
        // @ts-ignore - optional diagnostics exposed by the service
        this.errorDetail =
          (this.seriesSvc as any).lastErrorDetail ||
          (typeof err?.error === 'string'
            ? err.error
            : JSON.stringify(err?.error ?? {}, null, 2));
      },
      complete: () => {
        console.timeEnd('[MarketChart] /v1/series');
        this.loading = false;
      },
    });
  }

  // ---------------- helpers ----------------

  private formatError(err: any): string {
    if (err?.status) {
      const body =
        typeof err?.error === 'string'
          ? err.error.slice(0, 240)
          : JSON.stringify(err?.error || {}, null, 2).slice(0, 240);
      return `HTTP ${err.status}: ${err.statusText || ''} ${body}`;
    }
    return 'Unexpected error (see console)';
  }

  private buildOptions(body: SeriesResponse): EChartsOption {
    // x-axis: timestamps as returned (string ISO or number)
    const xs = body.series.map(([t]) => t);
    const price = body.series.map(([t, v]) => [t, v]);

    const series: any[] = [
      {
        name: `${body.asset} price`,
        type: 'line',
        showSymbol: false,
        smooth: false,
        data: price,
        z: 2,
      },
    ];

    // Indicators
    const ind = body.indicators || {};

    // Add SMA 50
    if (this.showSMA50 && ind['sma_50']?.length) {
      const sma50 = ind['sma_50'].map((v, i) => [xs[i], v]);
      series.push({
        name: 'SMA 50',
        type: 'line',
        showSymbol: false,
        smooth: false,
        data: sma50,
        lineStyle: { width: 1 },
        z: 1,
      });
    }

    // Add SMA 200
    if (this.showSMA200 && ind['sma_200']?.length) {
      const sma200 = ind['sma_200'].map((v, i) => [xs[i], v]);
      series.push({
        name: 'SMA 200',
        type: 'line',
        showSymbol: false,
        smooth: false,
        data: sma200,
        lineStyle: { width: 1 },
        z: 1,
      });
    }

    // Add anomaly dots (scatter)
    if (this.showAnomalies && Array.isArray(body.anomalies) && body.anomalies.length === body.series.length) {
      const dots = body.series
        .map(([t, v], i) => (body.anomalies![i] ? [t, v] : null))
        .filter(Boolean) as [string | number, number][];
      if (dots.length) {
        series.push({
          name: 'Anomalies',
          type: 'scatter',
          symbolSize: 8,
          data: dots,
          z: 3,
        });
      }
    }

    const options: EChartsOption = {
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'cross' },
      },
      legend: { top: 0 },
      grid: { left: 40, right: 20, top: 30, bottom: 40 },
      xAxis: { type: 'category', boundaryGap: false, data: xs },
      yAxis: { type: 'value', scale: true },
      series,
      dataZoom: [
        { type: 'inside', start: 60, end: 100 },
        { type: 'slider', start: 60, end: 100 },
      ],
    };

    return options;
  }
}
