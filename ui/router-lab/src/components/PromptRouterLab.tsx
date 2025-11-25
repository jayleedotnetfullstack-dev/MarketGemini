// src/components/PromptRouterLab.tsx

import React, { useState } from "react";
import {
  DigestResult,
  RouterChatResponse,
  Provider,
  ProviderOption,
  ConsolidateConfig,
  ProfileId,
} from "./RouterTypes";
import { PROVIDER_CONFIG } from "./ProviderConfig";
import ProviderSelector from "./ProviderSelector";
import ConsolidationSelector from "./ConsolidationSelector";
import DigestSummary from "./DigestSummary";
import ChatResponse from "./ChatResponse";
import DebugPanel from "./DebugPanel";

const ROUTER_BASE_URL = "http://localhost:8000";

const PromptRouterLab: React.FC = () => {
  const [prompt, setPrompt] = useState("");
  const [digest, setDigest] = useState<DigestResult | null>(null);
  const [digestRaw, setDigestRaw] = useState<any | null>(null);
  const [routerResponse, setRouterResponse] =
    useState<RouterChatResponse | null>(null);
  const [chatRaw, setChatRaw] = useState<any | null>(null);

  const [loadingDigest, setLoadingDigest] = useState(false);
  const [loadingChat, setLoadingChat] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Toggle: show individual model outputs vs just final consolidated result
  const [showProviderDetails, setShowProviderDetails] = useState<boolean>(false);

  const enabledProviderOptions: ProviderOption[] = PROVIDER_CONFIG
    .filter((p) => p.enabled)
    .map((p) => ({ provider: p.provider, label: p.label }));

  // Default: Gemini only (you can multi-select in ProviderSelector)
  const [providers, setProviders] = useState<Provider[]>(["gemini"]);

  const [consolidateConfig, setConsolidateConfig] = useState<ConsolidateConfig>(
    {
      enabled: true,
      provider: "gemini",
      model: "gemini-3.0-flash",
    }
  );

  // --- Handlers ---

  const handleAnalyze = async () => {
    setError(null);
    setDigest(null);
    setDigestRaw(null);
    setRouterResponse(null);
    setChatRaw(null);

    if (!prompt.trim()) {
      setError("Please enter a prompt first.");
      return;
    }

    setLoadingDigest(true);
    try {
      const body = {
        user_id: "router-lab",
        session_id: "router-lab-session-1",
        messages: [
          {
            role: "user",
            content: prompt,
          },
        ],
      };

      const resp = await fetch(`${ROUTER_BASE_URL}/v1/digest`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(body),
      });

      const data = await resp.json();
      setDigestRaw(data);

      if (!resp.ok) {
        setError(`Digest error: ${resp.status} ${resp.statusText}`);
        return;
      }

      const profile: ProfileId = (data.profile as ProfileId) ?? "summary";

      const parsed: DigestResult = {
        intent: data.intent ?? "unknown",
        profile,
        confidence: typeof data.confidence === "number" ? data.confidence : 0.0,
        cleaned_prompt: data.cleaned_prompt ?? prompt,
        suggestions: Array.isArray(data.suggestions) ? data.suggestions : [],
      };

      setDigest(parsed);
    } catch (e: any) {
      console.error("Digest error:", e);
      setError(e.message || "Digest error");
      setDigestRaw({ error: e.message || String(e) });
    } finally {
      setLoadingDigest(false);
    }
  };

  const handleRunChat = async () => {
    setError(null);
    setLoadingChat(true);
    setRouterResponse(null);
    setChatRaw(null);

    const finalPrompt = digest?.cleaned_prompt?.trim() || prompt.trim();
    if (!finalPrompt) {
      setError("No prompt to send. Please analyze first or enter a prompt.");
      setLoadingChat(false);
      return;
    }

    if (providers.length === 0) {
      setError("Please select at least one provider.");
      setLoadingChat(false);
      return;
    }

    const profile: ProfileId = digest?.profile ?? "summary";

    try {
      const body = {
        // user_id will eventually come from auth; for now demo
        user_id: "router-lab",
        session_id: "router-lab-session-1",
        profile,
        providers, // multiple providers supported
        messages: [
          {
            role: "user",
            content: finalPrompt,
          },
        ],
        consolidate: {
          enabled: consolidateConfig.enabled,
          provider: consolidateConfig.provider,
          model: consolidateConfig.model,
        },
      };

      const resp = await fetch(`${ROUTER_BASE_URL}/v1/router/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(body),
      });

      const data = await resp.json();
      setChatRaw(data);

      if (!resp.ok) {
        setError(`Chat error: ${resp.status} ${resp.statusText}`);
        return;
      }

      // trust backend to match RouterChatResponse shape
      setRouterResponse(data as RouterChatResponse);
    } catch (e: any) {
      console.error("Chat error:", e);
      setError(e.message || "Chat error");
      setChatRaw({ error: e.message || String(e) });
    } finally {
      setLoadingChat(false);
    }
  };

  // --- UI ---

  return (
    <div
      style={{
        minHeight: "100vh",
        backgroundColor: "#020617",
        color: "#e5e7eb",
        padding: "24px",
        fontFamily:
          "system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
      }}
    >
      <div
        style={{
          maxWidth: "1100px",
          margin: "0 auto",
          display: "grid",
          gridTemplateColumns: "minmax(0, 2fr) minmax(0, 1.5fr)",
          gap: "24px",
        }}
      >
        {/* Left column */}
        <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
          <h1 style={{ fontSize: "24px", fontWeight: 700 }}>
            Prompt Router Lab
          </h1>
          <p style={{ fontSize: "14px", color: "#9ca3af" }}>
            Analyze a prompt, auto-select a profile, then run it through one or
            more providers (Gemini / ChatGPT / DeepSeek), with optional
            consolidation.
          </p>

          {/* Provider selector & consolidation */}
          <div
            style={{
              padding: "12px",
              borderRadius: "12px",
              border: "1px solid #1f2937",
              backgroundColor: "#020617",
            }}
          >
            <label
              style={{
                fontSize: "13px",
                fontWeight: 600,
                color: "#9ca3af",
                display: "block",
                marginBottom: "4px",
              }}
            >
              Providers
            </label>
            <ProviderSelector
              selected={providers}
              onChange={setProviders}
              options={enabledProviderOptions}
            />

            <div style={{ marginTop: "8px" }}>
              <ConsolidationSelector
                value={consolidateConfig}
                onChange={setConsolidateConfig}
              />
            </div>

            {/* Toggle per-provider debugging view */}
            <div
              style={{
                marginTop: "8px",
                display: "flex",
                alignItems: "center",
                gap: "8px",
                fontSize: "12px",
                color: "#9ca3af",
              }}
            >
              <label
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "6px",
                  cursor: "pointer",
                }}
              >
                <input
                  type="checkbox"
                  checked={showProviderDetails}
                  onChange={(e) =>
                    setShowProviderDetails(e.target.checked)
                  }
                />
                Show per-provider responses (debug)
              </label>
            </div>
          </div>

          {/* Prompt input */}
          <div
            style={{
              backgroundColor: "#020617",
              borderRadius: "12px",
              border: "1px solid #1f2937",
              padding: "12px",
            }}
          >
            <label
              style={{
                fontSize: "13px",
                fontWeight: 600,
                color: "#9ca3af",
                display: "block",
                marginBottom: "6px",
              }}
            >
              Prompt
            </label>
            <textarea
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="e.g. Summarize gold price drivers in 3 bullets."
              style={{
                width: "100%",
                minHeight: "110px",
                resize: "vertical",
                borderRadius: "8px",
                border: "1px solid #374151",
                backgroundColor: "#020617",
                color: "#e5e7eb",
                padding: "8px 10px",
                fontSize: "14px",
              }}
            />
            <div
              style={{
                marginTop: "8px",
                display: "flex",
                gap: "8px",
                alignItems: "center",
                justifyContent: "flex-start",
              }}
            >
              <button
                onClick={handleAnalyze}
                disabled={loadingDigest}
                style={{
                  padding: "6px 12px",
                  borderRadius: "999px",
                  border: "none",
                  background: "linear-gradient(to right, #06b6d4, #6366f1)",
                  color: "#0f172a",
                  fontWeight: 600,
                  fontSize: "13px",
                  cursor: loadingDigest ? "wait" : "pointer",
                  opacity: loadingDigest ? 0.6 : 1,
                }}
              >
                {loadingDigest ? "Analyzing..." : "Analyze / Digest"}
              </button>

              <button
                onClick={handleRunChat}
                disabled={loadingChat}
                style={{
                  padding: "6px 12px",
                  borderRadius: "999px",
                  border: "1px solid #4b5563",
                  backgroundColor: "transparent",
                  color: "#e5e7eb",
                  fontWeight: 500,
                  fontSize: "13px",
                  cursor: loadingChat ? "wait" : "pointer",
                  opacity: loadingChat ? 0.6 : 1,
                }}
              >
                {loadingChat ? "Running..." : "Run with cleaned prompt"}
              </button>
            </div>
          </div>

          {/* Error */}
          {error && (
            <div
              style={{
                backgroundColor: "#451a1a",
                border: "1px solid #b91c1c",
                color: "#fecaca",
                borderRadius: "10px",
                padding: "8px 10px",
                fontSize: "13px",
              }}
            >
              {error}
            </div>
          )}

          {/* Digest summary */}
          <DigestSummary digest={digest} />

          {/* Final + (optional) per-provider responses */}
          <ChatResponse
            routerResponse={routerResponse}
            showProviderDetails={showProviderDetails}
          />
        </div>

        {/* Right column: raw debug */}
        <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
          <DebugPanel title="Digest raw" data={digestRaw} />
          <DebugPanel title="Router chat raw" data={chatRaw} />
        </div>
      </div>
    </div>
  );
};

export default PromptRouterLab;
