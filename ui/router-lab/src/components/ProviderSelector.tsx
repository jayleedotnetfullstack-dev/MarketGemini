// src/components/ProviderSelector.tsx

import React from "react";
import type { Provider, ProviderOption } from "./RouterTypes";

interface ProviderSelectorProps {
  selected: Provider[];
  onChange: (providers: Provider[]) => void;
  options: ProviderOption[];
}

const ProviderSelector: React.FC<ProviderSelectorProps> = ({
  selected,
  onChange,
  options,
}) => {
  const toggle = (p: Provider) => {
    if (selected.includes(p)) {
      onChange(selected.filter((x) => x !== p));
    } else {
      onChange([...selected, p]);
    }
  };

  return (
    <div
      style={{
        marginTop: "8px",
        marginBottom: "12px",
        display: "flex",
        flexWrap: "wrap",
        gap: "8px",
      }}
    >
      {options.map((opt) => {
        const active = selected.includes(opt.provider);
        return (
          <button
            key={opt.provider}
            onClick={() => toggle(opt.provider)}
            style={{
              padding: "6px 12px",
              borderRadius: "999px",
              fontSize: "12px",
              border: active ? "2px solid #6366f1" : "1px solid #374151",
              backgroundColor: active ? "#111827" : "rgba(15,23,42,0.8)",
              color: "#e5e7eb",
              cursor: "pointer",
            }}
          >
            {opt.label}
          </button>
        );
      })}
    </div>
  );
};

export default ProviderSelector;
