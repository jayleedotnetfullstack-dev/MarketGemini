// src/app/app.routes.ts
import { Routes } from '@angular/router';
import { MarketChartComponent } from './components/market-chart/market-chart.component';

export const routes: Routes = [
  { path: '', pathMatch: 'full', redirectTo: 'chart' },
  { path: 'chart', component: MarketChartComponent },
];
