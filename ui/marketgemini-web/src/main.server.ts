// src/main.server.ts
import 'zone.js/node'; // ✅ required for server runtime
import { BootstrapContext, bootstrapApplication} from '@angular/platform-browser';
import { provideServerRendering } from '@angular/platform-server';
import { importProvidersFrom } from '@angular/core';
import { provideHttpClient } from '@angular/common/http';
import { provideRouter } from '@angular/router';

import { AppComponent } from './app/app.component';
import { routes } from './app/app.routes';

// ECharts provider (same as browser)
import { NgxEchartsModule } from 'ngx-echarts';

export default (context: BootstrapContext) =>
  bootstrapApplication(
    AppComponent,
    {
      providers: [
        provideServerRendering(),
        provideHttpClient(),
        provideRouter(routes),
        importProvidersFrom(
          NgxEchartsModule.forRoot({
            // Provides NGX_ECHARTS_CONFIG on the server too
            echarts: () => import('echarts'),
          })
        ),
      ],
    },
    // 🔴 This was missing — must pass the server BootstrapContext
    context,
  );
