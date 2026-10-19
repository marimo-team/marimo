/* Copyright 2026 Marimo. All rights reserved. */

import { assertNever } from "@/utils/assertNever";
import { shellQuote } from "@/utils/shell";
import type { PairConfig } from "@/core/config/pair";

export type AgentTab = "claude" | "codex" | "opencode" | "prompt";

export const TERMINAL_TABS = ["claude", "codex", "opencode"] as const;

export const AGENT_TABS = ["claude", "codex", "opencode", "prompt"] as const;

export const AGENT_LABELS: Record<AgentTab, string> = {
  claude: "Claude",
  codex: "Codex",
  opencode: "OpenCode",
  prompt: "Prompt",
};

/** How to invoke marimo: from the local checkout in dev, else via uvx. */
export function getMarimoCommand(): string {
  return import.meta.env.DEV ? "uv run marimo" : "uvx marimo@latest";
}

/** Identifies the specific running notebook to pair on. */
export interface ConnectionInfo {
  url: string;
  /** Stable Session ID for ordinary editor execution. */
  session?: string;
  /** The host notebook ID, when known. */
  notebook?: string;
}

/**
 * The shell command that wraps an agent CLI, delegating prompt generation to
 * `marimo pair prompt` so the terminal and CLI stay in sync.
 */
export function getTerminalCommand(
  agent: Exclude<AgentTab, "prompt">,
  { url, notebook, session }: ConnectionInfo,
  withToken: boolean,
  config?: PairConfig,
): string {
  const command = config?.command ?? getMarimoCommand();
  const base = [
    `${command} pair prompt`,
    `--url ${shellQuote(url)}`,
    notebook
      ? `--notebook ${shellQuote(notebook)}`
      : session
        ? `--session ${shellQuote(session)}`
        : "",
    withToken ? "--with-token" : "",
  ]
    .filter(Boolean)
    .join(" \\\n  ");
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
  { url, notebook, session }: ConnectionInfo,
  token: string | null,
  config?: PairConfig,
): string {
  const command = config?.command ?? getMarimoCommand();
  const templates = config?.templates;
  const authentication = token
    ? formatPrompt(
        templates?.token ??
          "\n\nFor authenticated notebook discovery, set `export MARIMO_TOKEN={token}` in the shell that runs marimo.",
        { token: shellQuote(token) },
      )
    : "";
  return formatPrompt(
    templates?.prompt ??
      "Pair with me on this running marimo notebook.\n\nURL: {url}\n{notebook}{session}\nRun `{command} pair --help` first.\nUse `{command}` for all marimo commands.{authentication}",
    {
      command,
      url,
      notebook: notebook
        ? formatPrompt(templates?.notebook ?? "Notebook: {notebook}\n", {
            notebook,
          })
        : "",
      session:
        session && !notebook
          ? formatPrompt(templates?.session ?? "Session: {session}\n", {
              session,
            })
          : "",
      authentication,
    },
  );
}

function formatPrompt(
  template: string,
  values: Record<string, string>,
): string {
  // Replace once so inserted file names or tokens cannot become placeholders.
  return template.replaceAll(
    /\{(\w+)\}/g,
    (placeholder, key: string) => values[key] ?? placeholder,
  );
}

/** Mask all but the last 4 chars of a token for display. */
export function maskToken(token: string): string {
  if (token.length <= 4) {
    return "****";
  }
  return `${"*".repeat(Math.min(token.length - 4, 8))}${token.slice(-4)}`;
}
