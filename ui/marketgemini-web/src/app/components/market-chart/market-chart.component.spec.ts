import { TestBed } from '@angular/core/testing';
import { of } from 'rxjs';
import type { EChartsOption } from 'echarts';

import { MarketChartComponent } from './market-chart.component';
import { SeriesService, SeriesResponse } from '../../services/series.service';

class MockSeriesService {
  printDiag() {}
  setToken(_: string) {}

  getSeries(asset: string, want: string[]) {
    // shape matches your current SeriesResponse
    const mock: SeriesResponse = {
      asset: (asset || 'GOLD').toUpperCase(),
      series: [
        ['2024-01-01', 10],
        ['2024-01-02', 12],
        ['2024-01-03', 11],
      ],
      indicators: {
        sma_50: [10, 10.5, 11],
        sma_200: [9.5, 10, 10.2],
      },
      anomalies: [false, true, false],
    };
    // sanity: ensure include_indicators request contains both
    expect(want).toContain('sma_50');
    expect(want).toContain('sma_200');
    return of(mock);
  }
}

describe('MarketChartComponent', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [MarketChartComponent],
      providers: [{ provide: SeriesService, useClass: MockSeriesService }],
    }).compileComponents();
  });

  it('adds SMA 50 and SMA 200 series when toggles are true', () => {
    const fixture = TestBed.createComponent(MarketChartComponent);
    const comp = fixture.componentInstance;

    // ensure toggles are on
    comp.showSMA50 = true;
    comp.showSMA200 = true;
    comp.showAnomalies = false;

    comp.load();    // triggers mocked SeriesService.getSeries
    fixture.detectChanges();

    const opts = comp.chartOptions as EChartsOption;
    const series = (opts.series || []) as any[];

    // base price line + SMA50 + SMA200 = 3
    expect(series.length).toBe(3);
    expect(series.some(s => s.name === 'SMA 50' && s.type === 'line')).toBeTrue();
    expect(series.some(s => s.name === 'SMA 200' && s.type === 'line')).toBeTrue();
    expect(series.some(s => s.name?.includes('price'))).toBeTrue();
  });

  it('omits SMA lines when toggles are false', () => {
    const fixture = TestBed.createComponent(MarketChartComponent);
    const comp = fixture.componentInstance;

    comp.showSMA50 = false;
    comp.showSMA200 = false;
    comp.showAnomalies = false;

    comp.load();
    fixture.detectChanges();

    const series = (comp.chartOptions.series || []) as any[];
    expect(series.length).toBe(1); // only price line
  });
});
