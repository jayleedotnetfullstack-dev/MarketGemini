// src/components/ConsolidationSelector.tsx

import React from "react";
import type { Provider, ConsolidateConfig } from "./RouterTypes";
import { PROVIDER_CONFIG } from "./ProviderConfig";

interface ConsolidationSelectorProps {
  value: ConsolidateConfig;
  onChange: (cfg: ConsolidateConfig) => void;
}

const ConsolidationSelector: React.FC<ConsolidationSelectorProps> = ({
  value,
  onChange,
}) => {
  const handleProviderChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const provider = e.target.value as Provider;
    const providerCfg = PROVIDER_CONFIG.find((p) => p.provider === provider);
    const defaultModel =
      providerCfg?.models.find((m) => m.enabled)?.id || value.model;
    onChange({
      ...value,
      provider,
      model: defaultModel,
    });
  };

  const handleModelChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    onChange({ ...value, model: e.target.value });
  };

  if (!value.enabled) {
    return null; // hide when disabled
  }

  const currentProviderCfg = PROVIDER_CONFIG.find(
    (p) => p.provider === value.provider
  );

  return (
    <div style={{ marginTop: "4px", marginBottom: "12px" }}>
      <div style={{ fontSize: "13px", color: "#9ca3af", marginBottom: "4px" }}>
        Consolidation model
      </div>
      <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
        <select
          value={value.provider}
          onChange={handleProviderChange}
          style={{
            backgroundColor: "#020617",
            color: "#e5e7eb",
            borderRadius: "6px",
            border: "1px solid #374151",
            padding: "4px 8px",
            fontSize: "13px",
          }}
        >
          {PROVIDER_CONFIG.filter((p) => p.enabled).map((p) => (
            <option key={p.provider} value={p.provider}>
              {p.label}
            </option>
          ))}
        </select>

        <select
          value={value.model}
          onChange={handleModelChange}
          style={{
            backgroundColor: "#020617",
            color: "#e5e7eb",
            borderRadius: "6px",
            border: "1px solid #374151",
            padding: "4px 8px",
            fontSize: "13px",
          }}
        >
          {currentProviderCfg?.models
            .filter((m) => m.enabled)
            .map((m) => (
              <option key={m.id} value={m.id}>
                {m.label}
              </option>
            ))}
        </select>
      </div>
    </div>
  );
};

export default ConsolidationSelector;
