import React, { useState } from "react";

const ROUTER_BASE_URL =
  import.meta.env.VITE_ROUTER_BASE_URL || "http://localhost:8081";

interface DigestResult {
  intent: string;
  profile: string;
  confidence: number;
  cleaned_prompt: string;
  suggestions: string[];
}

interface ChatResult {
  provider: string;
  model: string;
  mode: string;
  content: string;
  tokens_in: number;
  tokens_out: number;
  latency_ms: number;
  cost_usd: number;
  profile?: string;
}

const PromptRouterLab: React.FC = () => {
  const [prompt, setPrompt] = useState("");
  const [digest, setDigest] = useState<DigestResult | null>(null);
  const [digestRaw, setDigestRaw] = useState<any | null>(null);
  const [chatResult, setChatResult] = useState<ChatResult | null>(null);
  const [chatRaw, setChatRaw] = useState<any | null>(null);

  const [loadingDigest, setLoadingDigest] = useState(false);
  const [loadingChat, setLoadingChat] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // --- Handlers ---

  const handleAnalyze = async () => {
    setError(null);
    setDigest(null);
    setDigestRaw(null);
    setChatResult(null);
    setChatRaw(null);

    if (!prompt.trim()) {
      setError("Please enter a prompt first.");
      return;
    }

    setLoadingDigest(true);
    try {
      const body = {
        user_id: "router-lab", // demo user; in real app this comes from auth
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

      const parsed: DigestResult = {
        intent: data.intent ?? "unknown",
        profile: data.profile ?? "summary",
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
    setChatResult(null);
    setChatRaw(null);

    // Use cleaned prompt if we have it; otherwise original
    const finalPrompt = digest?.cleaned_prompt?.trim() || prompt.trim();
    if (!finalPrompt) {
      setError("No prompt to send. Please analyze first or enter a prompt.");
      setLoadingChat(false);
      return;
    }

    try {
      const body = {
        user_id: "router-lab",
        session_id: "router-lab-session-1",
        profile: digest?.profile ?? "summary",
        messages: [
          {
            role: "user",
            content: finalPrompt,
          },
        ],
      };

      const resp = await fetch(`${ROUTER_BASE_URL}/v1/chat`, {
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

      const parsed: ChatResult = {
        provider: data.provider ?? "router",
        model: data.model ?? "n/a",
        mode: data.mode ?? "UNKNOWN",
        content: data.content ?? "",
        tokens_in: data.tokens_in ?? 0,
        tokens_out: data.tokens_out ?? 0,
        latency_ms: data.latency_ms ?? 0,
        cost_usd: data.cost_usd ?? 0,
        profile: data.profile,
      };

      setChatResult(parsed);
    } catch (e: any) {
      console.error("Chat error:", e);
      setError(e.message || "Chat error");
      setChatRaw({ error: e.message || String(e) });
    } finally {
      setLoadingChat(false);
    }
  };

  // --- Render helpers ---

  const confidenceLabel = (c: number) => {
    if (c >= 0.8) return "High";
    if (c >= 0.5) return "Medium";
    return "Low";
  };

  const confidenceColor = (c: number) => {
    if (c >= 0.8) return "#16a34a"; // green
    if (c >= 0.5) return "#facc15"; // yellow
    return "#ef4444"; // red
  };

  // --- UI ---

  return (
    <div
      style={{
        minHeight: "100vh",
        backgroundColor: "#020617",
        color: "#e5e7eb",
        padding: "24px",
        fontFamily: "system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
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
        {/* Left column: Prompt + digest + chat */}
        <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
          <h1 style={{ fontSize: "24px", fontWeight: 700 }}>
            Prompt Router Lab
          </h1>
          <p style={{ fontSize: "14px", color: "#9ca3af" }}>
            Analyze a prompt, auto-select a profile, then run it end-to-end
            through your router (Gemini / others) with debug info.
          </p>

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
                  background:
                    "linear-gradient(to right, #06b6d4, #6366f1)",
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
          <div
            style={{
              backgroundColor: "#020617",
              borderRadius: "12px",
              border: "1px solid #1f2937",
              padding: "12px",
              minHeight: "80px",
            }}
          >
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                marginBottom: "6px",
              }}
            >
              <h2
                style={{
                  fontSize: "14px",
                  fontWeight: 600,
                  color: "#e5e7eb",
                }}
              >
                Digest summary
              </h2>
              {digest && (
                <span
                  style={{
                    fontSize: "12px",
                    padding: "2px 8px",
                    borderRadius: "999px",
                    border: "1px solid #374151",
                    color: confidenceColor(digest.confidence),
                  }}
                >
                  Confidence: {confidenceLabel(digest.confidence)} (
                  {digest.confidence.toFixed(2)})
                </span>
              )}
            </div>

            {!digest && (
              <p style={{ fontSize: "13px", color: "#6b7280" }}>
                Run <strong>Analyze / Digest</strong> to see intent, profile,
                and suggestions.
              </p>
            )}

            {digest && (
              <div style={{ fontSize: "13px", color: "#d1d5db" }}>
                <div style={{ marginBottom: "4px" }}>
                  <strong>Intent:</strong> {digest.intent}
                </div>
                <div style={{ marginBottom: "4px" }}>
                  <strong>Profile:</strong> {digest.profile}
                </div>
                <div style={{ marginBottom: "4px" }}>
                  <strong>Cleaned prompt:</strong>{" "}
                  <span style={{ color: "#e5e7eb" }}>
                    {digest.cleaned_prompt}
                  </span>
                </div>
                {digest.suggestions.length > 0 && (
                  <div style={{ marginTop: "6px" }}>
                    <strong>Suggestions:</strong>
                    <ul style={{ marginTop: "4px", paddingLeft: "18px" }}>
                      {digest.suggestions.map((s, idx) => (
                        <li key={idx} style={{ color: "#9ca3af" }}>
                          {s}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Chat response */}
          <div
            style={{
              backgroundColor: "#020617",
              borderRadius: "12px",
              border: "1px solid #1f2937",
              padding: "12px",
              minHeight: "80px",
            }}
          >
            <h2
              style={{
                fontSize: "14px",
                fontWeight: 600,
                color: "#e5e7eb",
                marginBottom: "6px",
              }}
            >
              LLM Response
            </h2>

            {!chatResult && (
              <p style={{ fontSize: "13px", color: "#6b7280" }}>
                After digest, click{" "}
                <strong>Run with cleaned prompt</strong> to call{" "}
                <code>/v1/chat</code>.
              </p>
            )}

            {chatResult && (
              <>
                <div
                  style={{
                    fontSize: "12px",
                    color: "#9ca3af",
                    marginBottom: "6px",
                  }}
                >
                  <span>
                    Provider: <strong>{chatResult.provider}</strong>
                  </span>
                  {" · "}
                  <span>
                    Model: <strong>{chatResult.model}</strong>
                  </span>
                  {" · "}
                  <span>
                    Profile: <strong>{chatResult.profile ?? "n/a"}</strong>
                  </span>
                  {" · "}
                  <span>
                    Cost: ${chatResult.cost_usd.toFixed(4)} ·{" "}
                    {chatResult.tokens_in} → {chatResult.tokens_out} tokens ·{" "}
                    {chatResult.latency_ms} ms
                  </span>
                </div>
                <div
                  style={{
                    borderRadius: "8px",
                    border: "1px solid #374151",
                    padding: "10px",
                    backgroundColor: "#020617",
                    whiteSpace: "pre-wrap",
                    fontSize: "13px",
                    color: "#e5e7eb",
                    maxHeight: "260px",      // 👈 limit height
                    overflowY: "auto",       // 👈 show vertical scroll bar if needed
                  }}
                >
                  {chatResult.content}
                </div>
              </>
            )}
          </div>
        </div>

        {/* Right column: raw debug */}
        <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
          <div
            style={{
              backgroundColor: "#020617",
              borderRadius: "12px",
              border: "1px solid #1f2937",
              padding: "12px",
            }}
          >
            <h2
              style={{
                fontSize: "14px",
                fontWeight: 600,
                color: "#e5e7eb",
                marginBottom: "6px",
              }}
            >
              Digest raw
            </h2>
            <pre
              style={{
                fontSize: "11px",
                backgroundColor: "#020617",
                color: "#9ca3af",
                borderRadius: "8px",
                padding: "8px",
                border: "1px solid #111827",
                maxHeight: "260px",
                overflow: "auto",
              }}
            >
              {digestRaw
                ? JSON.stringify(digestRaw, null, 2)
                : "<no digest yet>"}
            </pre>
          </div>

          <div
            style={{
              backgroundColor: "#020617",
              borderRadius: "12px",
              border: "1px solid #1f2937",
              padding: "12px",
            }}
          >
            <h2
              style={{
                fontSize: "14px",
                fontWeight: 600,
                color: "#e5e7eb",
                marginBottom: "6px",
              }}
            >
              Chat raw
            </h2>
            <pre
              style={{
                fontSize: "11px",
                backgroundColor: "#020617",
                color: "#9ca3af",
                borderRadius: "8px",
                padding: "8px",
                border: "1px solid #111827",
                maxHeight: "260px",
                overflow: "auto",
              }}
            >
              {chatRaw ? JSON.stringify(chatRaw, null, 2) : "<no chat yet>"}
            </pre>
          </div>
        </div>
      </div>
    </div>
  );
};

export default PromptRouterLab;
