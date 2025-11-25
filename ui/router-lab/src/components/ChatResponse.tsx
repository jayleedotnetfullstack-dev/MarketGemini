// src/components/ChatResponse.tsx

import React from "react";
import type { RouterChatResponse } from "./RouterTypes";

interface ChatResponseProps {
  routerResponse: RouterChatResponse | null;
  showProviderDetails: boolean;
}

const ChatResponse: React.FC<ChatResponseProps> = ({
  routerResponse,
  showProviderDetails,
}) => {
  return (
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
        Final LLM Response
      </h2>

      {!routerResponse && (
        <p style={{ fontSize: "13px", color: "#6b7280" }}>
          After digest, click <strong>Run with cleaned prompt</strong> to call{" "}
          <code>/v1/router/chat</code>.
        </p>
      )}

      {routerResponse && (
        <>
          {/* Strategy + final consolidated content */}
          <div
            style={{
              fontSize: "12px",
              color: "#9ca3af",
              marginBottom: "6px",
            }}
          >
            Strategy:{" "}
            <strong>
              {routerResponse.final.strategy === "single_model"
                ? "Single model"
                : routerResponse.final.strategy === "highest_confidence"
                ? "Highest confidence"
                : "Ensemble"}
            </strong>
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
              maxHeight: "260px",
              overflowY: "auto",
              marginBottom: "10px",
            }}
          >
            {routerResponse.final.content}
          </div>

          {/* Optional per-provider detail view (debug) */}
          {showProviderDetails && (
            <div
              style={{
                borderTop: "1px solid #1f2937",
                paddingTop: "8px",
                marginTop: "4px",
              }}
            >
              <div
                style={{
                  fontSize: "12px",
                  color: "#9ca3af",
                  marginBottom: "4px",
                }}
              >
                Per-provider responses:
              </div>

              {routerResponse.results.map((r, idx) => (
                <div
                  key={idx}
                  style={{
                    marginBottom: "10px",
                    padding: "8px",
                    borderRadius: "8px",
                    border: "1px solid #111827",
                    backgroundColor: "#020617",
                  }}
                >
                  <div
                    style={{
                      fontSize: "12px",
                      color: "#9ca3af",
                      marginBottom: "4px",
                    }}
                  >
                    <strong>{r.provider}</strong> · {r.model} · profile{" "}
                    <strong>{r.profile}</strong> · cost $
                    {r.cost_usd.toFixed(4)} · {r.tokens_in} → {r.tokens_out}{" "}
                    tokens · {r.latency_ms} ms
                    {typeof r.confidence === "number" && (
                      <>
                        {" "}
                        · confidence {r.confidence.toFixed(2)}
                      </>
                    )}
                  </div>
                  <div
                    style={{
                      fontSize: "13px",
                      color: "#e5e7eb",
                      whiteSpace: "pre-wrap",
                    }}
                  >
                    {r.content}
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
};

export default ChatResponse;
