import React from "react";

export type DeepseekMode = "auto" | "chat" | "v3" | "r1";

export interface DeepseekModeSelectorProps {
  value: DeepseekMode;
  onChange: (mode: DeepseekMode) => void;
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
}) => {
  const modes: DeepseekMode[] = ["auto", "chat", "v3", "r1"];

  return (
    <div className="flex flex-col gap-2">
      <div className="text-sm font-medium text-gray-700">
        DeepSeek Mode
      </div>
      <div className="flex flex-wrap gap-2">
        {modes.map((mode) => {
          const selected = value === mode;
          return (
            <button
              key={mode}
              type="button"
              onClick={() => onChange(mode)}
              className={[
                "px-3 py-1.5 rounded-full text-xs font-medium border transition",
                selected
                  ? "bg-blue-600 text-white border-blue-600 shadow-sm"
                  : "bg-white text-gray-700 border-gray-300 hover:bg-gray-50",
              ].join(" ")}
            >
              {labelMap[mode]}
            </button>
          );
        })}
      </div>
      <div className="text-xs text-gray-500">
        {modeDescriptions[value]}
      </div>
      {value !== "auto" && (
        <div className="text-[11px] text-amber-600 mt-1">
          Router will still show a confidence score if it thinks another mode is a better fit.
        </div>
      )}
    </div>
  );
};
