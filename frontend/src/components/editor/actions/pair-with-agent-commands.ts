/* Copyright 2026 Marimo. All rights reserved. */

import { assertNever } from "@/utils/assertNever";

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

/** How to invoke marimo: from the local checkout in dev, else via uvx. */
export function getMarimoCommand(): string {
  return import.meta.env.DEV ? "uv run marimo" : "uvx marimo@latest";
}

/**
 * POSIX-quote a value for safe embedding in a shell command. These commands are
 * meant to be copied into a terminal, so a url/token containing shell
 * metacharacters (`'`, `&`, `$(...)`, ...) must not break out of its argument.
 *
 * Mirrors Python's `shlex.quote` (used on the CLI side in
 * `marimo/_cli/pair/commands.py`) so both sides produce identical commands:
 * values that are already shell-safe are left as-is for readability, and
 * anything else is single-quoted with embedded quotes escaped as `'"'"'`.
 */
export function shellQuote(value: string): string {
  if (value === "") {
    return "''";
  }
  // Same "safe" character set as CPython's shlex.quote (ASCII \w plus a few).
  if (/^[\w@%+=:,./-]+$/.test(value)) {
    return value;
  }
  return `'${value.replaceAll("'", `'"'"'`)}'`;
}

/** Identifies the specific running notebook to pair on. */
export interface ConnectionInfo {
  url: string;
  /**
   * The current session id, so agents connect to *this* notebook rather than
   * guessing when multiple sessions are open on the same server.
   */
  sessionId: string;
}

/**
 * The shell command that wraps an agent CLI, delegating prompt generation to
 * `marimo pair prompt` so the terminal and CLI stay in sync.
 */
export function getTerminalCommand(
  agent: Exclude<AgentTab, "prompt">,
  { url, sessionId }: ConnectionInfo,
  withToken: boolean,
): string {
  const tokenFlag = withToken ? " --with-token" : "";
  const base = `${getMarimoCommand()} pair prompt --url ${shellQuote(url)} --session ${shellQuote(sessionId)}${tokenFlag}`;
  switch (agent) {
    case "claude":
      return `claude "$(${base} --claude)"`;
    case "codex":
      return `codex "$(${base} --codex)"`;
    case "opencode":
      return `opencode --prompt "$(${base} --opencode)"`;
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
  { url, sessionId }: ConnectionInfo,
  token: string | null,
): string {
  const executeCmd = `execute-code.sh --url ${shellQuote(url)} --session ${shellQuote(sessionId)}`;
  const tokenHint = token
    ? `\n\nUse this auth token when calling \`execute-code.sh\`: \`${executeCmd} --token ${shellQuote(token)}\`.`
    : "";
  return [
    "Use the /marimo-pair skill to pair-program on a running marimo notebook.",
    "",
    `Connect to the notebook at: ${url} (session ${sessionId})`,
    "",
    `Use \`${executeCmd}\` from the marimo-pair skill to execute code in the notebook.${tokenHint}`,
    "",
    "Once you are connected, send a fun toast (mo.status.toast(...)) to the user inside marimo letting them know you're ready to pair.",
  ].join("\n");
}

/** Mask all but the last 4 chars of a token for display. */
export function maskToken(token: string): string {
  if (token.length <= 4) {
    return "****";
  }
  return `${"*".repeat(Math.min(token.length - 4, 8))}${token.slice(-4)}`;
}
