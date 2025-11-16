// ui/router-lab/src/App.tsx
import React, { useState } from "react";
import PromptRouterLab from "./components/PromptRouterLab";

const App: React.FC = () => {
  const [isDark, setIsDark] = useState(false);

  const bgColor = isDark ? "#020617" : "#f1f5f9"; // slate-950 / slate-100
  const textColor = isDark ? "#e5e7eb" : "#111827"; // slate-200 / gray-900
  const cardBg = isDark ? "#020617" : "#ffffff";
  const borderColor = isDark ? "#1f2937" : "#e5e7eb";

  return (
    <div
      className="min-h-screen"
      style={{ backgroundColor: bgColor, color: textColor }}
    >
      <header
        className="px-4 py-3 border-b flex items-center justify-between"
        style={{ borderColor }}
      >
        <div>
          <h1 className="text-lg font-semibold">
            MarketGemini – Prompt Router Lab
          </h1>
          <p className="text-xs" style={{ opacity: 0.7 }}>
            Test prompt digestion, confidence, rewrite suggestions, provider routing
            and cost/debug info.
          </p>
        </div>
        <button
          onClick={() => setIsDark((v) => !v)}
          className="px-3 py-1 text-xs rounded-md border"
          style={{
            backgroundColor: cardBg,
            borderColor,
          }}
        >
          {isDark ? "☀ Light" : "🌙 Dark"}
        </button>
      </header>

      <main className="p-4">
        <PromptRouterLab isDark={isDark} />
      </main>
    </div>
  );
};

export default App;
