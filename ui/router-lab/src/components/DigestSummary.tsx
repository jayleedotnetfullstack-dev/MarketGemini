// src/components/DigestSummary.tsx

import React from "react";
import type { DigestResult } from "./RouterTypes";

interface DigestSummaryProps {
  digest: DigestResult | null;
}

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

const DigestSummary: React.FC<DigestSummaryProps> = ({ digest }) => {
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
          Run <strong>Analyze / Digest</strong> to see intent, profile, and
          suggestions.
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
            <span style={{ color: "#e5e7eb" }}>{digest.cleaned_prompt}</span>
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
  );
};

export default DigestSummary;
