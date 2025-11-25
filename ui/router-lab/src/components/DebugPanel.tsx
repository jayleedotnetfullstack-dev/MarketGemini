// src/components/DebugPanel.tsx

import React from "react";

interface DebugPanelProps {
  title: string;
  data: any;
  placeholder?: string;
}

const DebugPanel: React.FC<DebugPanelProps> = ({
  title,
  data,
  placeholder = "<no data>",
}) => {
  return (
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
        {title}
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
        {data ? JSON.stringify(data, null, 2) : placeholder}
      </pre>
    </div>
  );
};

export default DebugPanel;
