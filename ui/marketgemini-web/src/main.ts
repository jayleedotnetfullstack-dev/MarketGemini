// src/main.ts
import 'zone.js'; // ✅ required for browser runtime
import { bootstrapApplication } from '@angular/platform-browser';
import { importProvidersFrom } from '@angular/core';
import { provideHttpClient, withFetch } from '@angular/common/http'; // ⬅️ add withFetch
import { provideRouter } from '@angular/router';

import { AppComponent } from './app/app.component';
import { routes } from './app/app.routes';

import { NgxEchartsModule } from 'ngx-echarts';

bootstrapApplication(AppComponent, {
  providers: [
    provideHttpClient(withFetch()),   // ✅ enable fetch for SSR
    provideRouter(routes),

    // ✅ Registers the NGX_ECHARTS_CONFIG provider at app bootstrap.
    importProvidersFrom(
      NgxEchartsModule.forRoot({
        echarts: () => import('echarts'),
      })
    ),
  ],
})
  .then(() => console.log('[bootstrap] ngx-echarts provider registered'))
  .catch(err => console.error(err));
