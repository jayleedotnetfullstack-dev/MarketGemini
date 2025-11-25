// src/components/ProviderConfig.ts

import type { Provider } from "./RouterTypes";

export interface ModelConfig {
  id: string;        // e.g. "gemini-3.0-flash"
  label: string;     // human label
  enabled: boolean;
}

export interface ProviderConfig {
  provider: Provider;
  label: string;
  enabled: boolean;
  models: ModelConfig[];
}

// Frontend config; later you can serve this from backend
export const PROVIDER_CONFIG: ProviderConfig[] = [
  {
    provider: "gemini",
    label: "Gemini",
    enabled: true,
    models: [
      { id: "gemini-2.5-flash", label: "Gemini 2.5 Flash", enabled: false },
      { id: "gemini-3.0-flash", label: "Gemini 3.0 Flash", enabled: true },
    ],
  },
  {
    provider: "openai",
    label: "ChatGPT",
    enabled: true,
    models: [
      { id: "gpt-4.1-mini", label: "GPT-4.1 Mini", enabled: true },
      { id: "gpt-5", label: "GPT-5", enabled: true },
    ],
  },
  {
    provider: "deepseek",
    label: "DeepSeek",
    enabled: true,
    models: [
      { id: "deepseek-r1", label: "DeepSeek R1", enabled: true },
    ],
  },
];
