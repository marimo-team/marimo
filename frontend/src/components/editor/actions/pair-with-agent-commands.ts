/* Copyright 2026 Marimo. All rights reserved. */

import { assertNever } from "@/utils/assertNever";
import { KnownQueryParams } from "@/core/constants";
import type { SessionId } from "@/core/kernel/session";
import { shellQuote } from "@/utils/shell";

export type AgentTab = "claude" | "codex" | "opencode" | "prompt";

export const TERMINAL_TABS = ["claude", "codex", "opencode"] as const;

export const AGENT_TABS = ["claude", "codex", "opencode", "prompt"] as const;

export const AGENT_LABELS: Record<AgentTab, string> = {
  claude: "Claude",
  codex: "Codex",
  opencode: "OpenCode",
  prompt: "Prompt",
};

export const SKILL_INSTALL = "npx skills add marimo-team/marimo-pair";

/** Invoke marimo from the same project environment as the notebook server. */
export function getMarimoCommand(): string {
  return "uv run marimo";
}

/** Return the server file key from a page URL, preserving its decoded value. */
export function getFileFromURL(href: string): string | undefined {
  const file = new URL(href).searchParams.get(KnownQueryParams.filePath);
  return file === null || file === "" ? undefined : file;
}

function getFileFlag(file: string | undefined): string {
  return file ? ` --file ${shellQuote(file)}` : "";
}

/** Identifies the specific running notebook to pair on. */
export interface ConnectionInfo {
  url: string;
  sessionId: SessionId;
  /** The server's file key, when the page URL identifies a notebook. */
  file?: string;
}

/**
 * The shell command that wraps an agent CLI, delegating prompt generation to
 * `marimo pair prompt` so the terminal and CLI stay in sync.
 */
export function getTerminalCommand(
  agent: Exclude<AgentTab, "prompt">,
  { url, sessionId, file }: ConnectionInfo,
  withToken: boolean,
): string {
  const fileFlag = getFileFlag(file);
  const tokenFlag = withToken ? " --with-token" : "";
  const base = `${getMarimoCommand()} pair prompt --url ${shellQuote(url)} --session ${shellQuote(sessionId)}${fileFlag}${tokenFlag}`;
  switch (agent) {
    case "claude":
      return `claude "$(${base})"`;
    case "codex":
      return `codex "$(${base})"`;
    case "opencode":
      return `opencode --prompt "$(${base})"`;
    default:
      assertNever(agent);
  }
}

/**
 * The raw prompt for the "Prompt" tab. Mirrors the output of
 * `marimo pair prompt` (see `marimo/_cli/pair/commands.py`) so pasting it into
 * an agent behaves the same as the terminal commands.
 */
export function getRawPrompt(
  { url, sessionId, file }: ConnectionInfo,
  hasToken: boolean,
): string {
  const targetLines = [
    "Pair with the live marimo notebook at this target:",
    `  Server: ${url}`,
    `  Session: ${sessionId}`,
  ];
  if (file) {
    targetLines.push(`  Notebook: ${file}`);
  }

  return [
    ...targetLines,
    "",
    "Start with: marimo pair --help",
    "If marimo is not on your PATH, run it the same way this notebook server was started.",
    ...(hasToken
      ? [
          "",
          "This notebook uses authentication. Run the terminal command with --with-token and paste its output here instead.",
        ]
      : []),
    "",
    'Once connected, run `import marimo as mo; mo.status.toast("Ready to pair")` to let the user know you are ready.',
  ].join("\n");
}

/** Mask all but the last 4 chars of a token for display. */
export function maskToken(token: string): string {
  if (token.length <= 4) {
    return "****";
  }
  return `${"*".repeat(Math.min(token.length - 4, 8))}${token.slice(-4)}`;
}
