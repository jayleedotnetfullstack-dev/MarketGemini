import React, { useState } from "react";

export type DeepseekMode = "auto" | "chat" | "v3" | "r1";

export interface DeepseekModeSelectorProps {
  // selected modes (multi-select). "auto" acts as exclusive shortcut.
  value: DeepseekMode[];
  onChange: (modes: DeepseekMode[]) => void;

  // optional: which mode will be used for consolidation (separate from selected modes)
  consolidateMode?: DeepseekMode;
  onConsolidateChange?: (mode: DeepseekMode) => void;

  // optional runtime info (populated after calls)
  modeCosts?: Partial<Record<DeepseekMode, number>>;
  modeStatuses?: Partial<Record<DeepseekMode, "idle" | "running" | "success" | "failed">>;
  modeLogs?: Partial<Record<DeepseekMode, string>>;

  // show debug/expand toggles per mode
  showDebug?: boolean;

  disabled?: boolean;
}

const modeDescriptions: Record<DeepseekMode, string> = {
  auto: "Let the router choose between Chat / V3 / R1 based on your prompt.",
  chat: "Fast, cheap, general-purpose chat (everyday Q&A, explanation, guidance).",
  v3: "Stronger reasoning & coding than Chat; good for complex tasks, analysis.",
  r1: "Think-aloud chain-of-thought for hard reasoning; slower & more verbose.",
};

const labelMap: Record<DeepseekMode, string> = {
  auto: "Auto (Recommended)",
  chat: "Chat",
  v3: "V3",
  r1: "R1 (Reasoning)",
};

export const DeepseekModeSelector: React.FC<DeepseekModeSelectorProps> = ({
  value,
  onChange,
  consolidateMode,
  onConsolidateChange,
  modeCosts = {},
  modeStatuses = {},
  modeLogs = {},
  showDebug = false,
  disabled = false,
}) => {
  const modes: DeepseekMode[] = ["auto", "chat", "v3", "r1"];
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});

  const isSelected = (m: DeepseekMode) => value.includes(m);

  const toggleMode = (mode: DeepseekMode) => {
    if (disabled) return;
    // "auto" is exclusive: selecting it clears others, selecting any other removes auto
    if (mode === "auto") {
      onChange(["auto"]);
      return;
    }

    const next = new Set(value.filter((v) => v !== "auto"));
    if (next.has(mode)) next.delete(mode);
    else next.add(mode);
    onChange(Array.from(next) as DeepseekMode[]);
  };

  const toggleExpand = (mode: DeepseekMode) =>
    setExpanded((s) => ({ ...s, [mode]: !s[mode] }));

  const statusColor = (s?: string) => {
    switch (s) {
      case "running":
        return "bg-yellow-400";
      case "success":
        return "bg-green-500";
      case "failed":
        return "bg-red-500";
      default:
        return "bg-gray-300";
    }
  };

  return (
    <div className="flex flex-col gap-2">
      <div className="text-sm font-medium text-gray-700">DeepSeek Modes</div>

      <div className="flex flex-wrap gap-2">
        {modes.map((mode) => {
          const selected = isSelected(mode);
          const status = modeStatuses[mode];
          const cost = modeCosts[mode];
          return (
            <div key={mode} className="flex flex-col">
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => toggleMode(mode)}
                  disabled={disabled}
                  className={[
                    "px-3 py-1.5 rounded-full text-xs font-medium border transition flex items-center gap-2",
                    selected
                      ? "bg-blue-600 text-white border-blue-600 shadow-sm"
                      : "bg-white text-gray-700 border-gray-300 hover:bg-gray-50",
                  ].join(" ")}
                >
                  <span>{labelMap[mode]}</span>

                  {/* cost placeholder */}
                  {cost !== undefined && (
                    <span className="ml-2 text-[11px] px-1 rounded bg-white/10">
                      ${Number(cost).toFixed(2)}
                    </span>
                  )}

                  {/* status dot */}
                  <span
                    title={status ?? "idle"}
                    className={[
                      "w-2 h-2 rounded-full inline-block ml-2",
                      statusColor(status),
                    ].join(" ")}
                  />
                </button>

                {/* consolidate selector (radio-like) */}
                {onConsolidateChange && (
                  <button
                    title="Use this mode to consolidate answers"
                    type="button"
                    onClick={() => onConsolidateChange(mode)}
                    className={[
                      "px-2 py-1 text-[11px] rounded border",
                      consolidateMode === mode
                        ? "bg-indigo-600 text-white border-indigo-600"
                        : "bg-white text-gray-600 border-gray-200 hover:bg-gray-50",
                    ].join(" ")}
                  >
                    {consolidateMode === mode ? "Consolidator" : "Set"}
                  </button>
                )}

                {/* debug toggle */}
                {showDebug && (
                  <button
                    type="button"
                    onClick={() => toggleExpand(mode)}
                    className="px-2 py-1 text-[11px] rounded border bg-white text-gray-600 border-gray-200 hover:bg-gray-50"
                  >
                    {expanded[mode] ? "Hide" : "Logs"}
                  </button>
                )}
              </div>

              {/* debug/log area */}
              {showDebug && expanded[mode] && (
                <div className="mt-1 p-2 bg-gray-50 border border-gray-100 rounded text-xs text-gray-700 w-[360px]">
                  <div className="font-medium text-[11px] mb-1">{labelMap[mode]} — Info</div>
                  <div className="text-[11px] text-gray-500 mb-2">{modeDescriptions[mode]}</div>
                  <div className="text-[11px]">
                    <strong>Status:</strong> {status ?? "idle"}{" "}
                    <span className="mx-2">|</span>
                    <strong>Cost:</strong> {cost !== undefined ? `$${Number(cost).toFixed(2)}` : "—"}
                  </div>
                  <pre className="mt-2 overflow-auto text-[11px] whitespace-pre-wrap">
                    {modeLogs[mode] ?? "No logs available."}
                  </pre>
                </div>
              )}
            </div>
          );
        })}
      </div>

      <div className="text-xs text-gray-500">{modeDescriptions[value[0] ?? "auto"]}</div>

      {/* small hint for non-auto selections */}
      {!(value.length === 1 && value[0] === "auto") && (
        <div className="text-[11px] text-amber-600 mt-1">
          Multiple modes selected — each will run and contribute to consolidation.
        </div>
      )}
    </div>
  );
};
