/* Copyright 2026 Marimo. All rights reserved. */

import { assertNever } from "@/utils/assertNever";
import { KnownQueryParams } from "@/core/constants";
import { shellQuote } from "@/utils/shell";
import type { PairPreviewConfig } from "@/core/config/pair";

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
  /** The server's file key or notebook filename, when known. */
  file?: string;
  session?: string;
}

/**
 * The shell command that wraps an agent CLI, delegating prompt generation to
 * `marimo pair prompt` so the terminal and CLI stay in sync.
 */
export function getTerminalCommand(
  agent: Exclude<AgentTab, "prompt">,
  { url, file, session }: ConnectionInfo,
  withToken: boolean,
  preview?: PairPreviewConfig,
): string {
  const command = preview?.command ?? getMarimoCommand();
  const prefix = preview ? "MARIMO_PAIR_NEXT=1 " : "";
  const base = [
    `${prefix}${command} pair prompt`,
    `--url ${shellQuote(url)}`,
    file ? `--file ${shellQuote(file)}` : "",
    preview && session ? `--session ${shellQuote(session)}` : "",
    withToken ? "--with-token" : "",
    preview ? "" : `--${agent}`,
  ]
    .filter(Boolean)
    .join(preview ? " \\\n  " : " ");
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
  { url, file, session }: ConnectionInfo,
  token: string | null,
  preview?: PairPreviewConfig,
): string {
  if (preview) {
    const { command, templates } = preview;
    return formatPrompt(templates.prompt, {
      command,
      url,
      file: file ? formatPrompt(templates.file, { file }) : "",
      session: session ? formatPrompt(templates.session, { session }) : "",
      authentication: token
        ? formatPrompt(templates.token, { token: shellQuote(token) })
        : "",
    });
  }

  const fileFlag = getFileFlag(file);
  const fileHint = file ? ` (file ${file})` : "";
  const executeCmd = `execute-code.sh --url ${shellQuote(url)}${fileFlag}`;
  const tokenHint = token
    ? `\n\nUse this auth token when calling \`execute-code.sh\`: \`${executeCmd} --token ${shellQuote(token)}\`.`
    : "";
  return [
    "Use the /marimo-pair skill to pair-program on a running marimo notebook.",
    "",
    `Connect to the notebook at: ${url}${fileHint}`,
    "",
    `Use \`${executeCmd}\` from the marimo-pair skill to execute code in the notebook.${tokenHint}`,
    "",
    "Once you are connected, send a fun toast (mo.status.toast(...)) to the user inside marimo letting them know you're ready to pair.",
  ].join("\n");
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
