import { test, expect } from '@playwright/test';

test.describe('Market chart', () => {
  test('shows SMA 50 & 200 after Reload (mocked backend)', async ({ page }) => {
    // 1) Capture series names via a bridge function
    let captured: string[] = [];
    await page.exposeFunction('__reportSeries', (names: string[]) => {
      captured = Array.isArray(names) ? names : [];
    });

    // 2) Init script: enable debug + provide default bridge + MG_API
    await page.addInitScript(() => {
      localStorage.setItem('mg_debug', '1');
      // default bridge saves to window for manual inspection
      (window as any).__reportSeries = (window as any).__reportSeries || ((names: any) => {
        (window as any).__mgSeriesNames = names;
      });
      // make API origin predictable if your UI reads it
      (window as any).MG_API = location.origin;
    });

    // 3) Mock backend: match either with or without querystring
    await page.route('**/v1/series**', async route => {
      const mock = {
        asset: 'GOLD',
        series: Array.from({ length: 10 }, (_, i) => [
          `2025-01-${String(i + 1).padStart(2, '0')}`,
          100 + i
        ]),
        indicators: {
          sma_50: Array.from({ length: 10 }, (_, i) => 100 + i * 0.5),
          sma_200: Array.from({ length: 10 }, (_, i) => 100 + i * 0.2),
        },
        anomalies: Array(10).fill(false)
      };
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mock),
      });
    });

    // 4) Optional: surface relevant console logs from the browser
    page.on('console', msg => {
      if (/\[(MarketChart|SeriesService)]/.test(msg.text())) {
        console.log('[browser]', msg.text());
      }
    });

    // 5) Navigate and trigger Reload
    await page.goto('http://localhost:4200/chart');
    await page.getByRole('button', { name: /reload/i }).click();

    // 6) Wait for the bridge or the legacy global to populate
    await page.waitForFunction(() => {
      const v = (window as any).__mgSeriesNames;
      return Array.isArray(v) && v.length >= 1;
    }, { timeout: 5000 }).catch(() => { /* ignore; we’ll use captured */ });

    // 7) Prefer bridge, fallback to window
    const names = captured.length
      ? captured
      : await page.evaluate(() => (window as any).__mgSeriesNames ?? []);

    // Debug dump on failure
    if (!names.length) {
      console.log('⚠️ DEBUG: names empty, dumping state...');
      await page.evaluate(() => {
        console.log('__mgSeriesNames:', (window as any).__mgSeriesNames);
        console.log('localStorage:', JSON.stringify(localStorage, null, 2));
      });
    }

    // 8) Assertions
    expect(names).toContain('SMA 50');
    expect(names).toContain('SMA 200');
    expect(names.some(n => (n || '').toLowerCase().includes('price'))).toBeTruthy();
  });
});
