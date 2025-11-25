// src/components/RouterTypes.ts

export type Provider = "gemini" | "openai" | "deepseek";

export interface ProviderOption {
  provider: Provider;
  label: string;
}

export type ProfileId = "factual" | "summary" | "creative" | "code";

// Digest coming from /v1/digest
export interface DigestResult {
  intent: string;
  profile: ProfileId;      // normalized downstream
  confidence: number;
  cleaned_prompt: string;
  suggestions: string[];
}

// Base model call result (per provider)
export interface BaseModelResult {
  provider: Provider;
  model: string;
  profile: ProfileId;      // user-selected
  content: string;
  tokens_in: number;
  tokens_out: number;
  latency_ms: number;
  cost_usd: number;
  confidence?: number | null;
}

// Router-level response shape

export interface RouterResultItem extends BaseModelResult {
  // can extend later with raw metadata
}

export interface FinalResult {
  content: string;
  strategy: "single_model" | "highest_confidence" | "ensemble";
}

export interface RouterChatResponse {
  final: FinalResult;
  results: RouterResultItem[];
}

// Consolidation config sent to backend
export interface ConsolidateConfig {
  enabled: boolean;
  provider: Provider;
  model: string;
}
