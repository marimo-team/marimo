import type { ResolvedTheme } from "@/theme/useTheme";

// Terminal theme configuration
export function createTerminalTheme(theme: ResolvedTheme) {
  const baseTheme = {
    cursor: "#ffffff",
    cursorAccent: "#000000",
  };

  return theme === "dark"
    ? {
        ...baseTheme,
        background: "#0f172a", // slate-900
        foreground: "#f8fafc", // slate-50
        black: "#0f172a",
        red: "#ef4444",
        green: "#22c55e",
        yellow: "#eab308",
        blue: "#3b82f6",
        magenta: "#a855f7",
        cyan: "#06b6d4",
        white: "#f1f5f9",
        brightBlack: "#475569",
        brightRed: "#f87171",
        brightGreen: "#4ade80",
        brightYellow: "#facc15",
        brightBlue: "#60a5fa",
        brightMagenta: "#c084fc",
        brightCyan: "#22d3ee",
        brightWhite: "#ffffff",
        selection: "rgba(148, 163, 184, 0.3)", // slate-400 with opacity
      }
    : {
        ...baseTheme,
        background: "#ffffff", // white
        foreground: "#0f172a", // slate-900
        cursor: "#0f172a",
        black: "#0f172a",
        red: "#dc2626",
        green: "#16a34a",
        yellow: "#ca8a04",
        blue: "#2563eb",
        magenta: "#9333ea",
        cyan: "#0891b2",
        white: "#e2e8f0",
        brightBlack: "#64748b",
        brightRed: "#ef4444",
        brightGreen: "#22c55e",
        brightYellow: "#eab308",
        brightBlue: "#3b82f6",
        brightMagenta: "#a855f7",
        brightCyan: "#06b6d4",
        brightWhite: "#ffffff",
        selection: "rgba(71, 85, 105, 0.2)", // slate-600 with opacity
      };
}
