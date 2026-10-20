/* Copyright 2026 Marimo. All rights reserved. */

import { afterEach, describe, expect, it, vi } from "vitest";
import { PAIR_CONFIG } from "@/__tests__/fixtures/pair-config";
import { shellQuote } from "@/utils/shell";
import {
  type ConnectionInfo,
  getMarimoCommand,
  getRawPrompt,
  getTerminalCommand,
  maskToken,
} from "../pair-with-agent-commands";

const CONNECTION: ConnectionInfo = {
  url: "http://localhost:8000",
  notebook: "nb-one",
};
const CONNECTION_WITHOUT_TARGET: ConnectionInfo = {
  url: "http://localhost:8000",
};

describe("shellQuote", () => {
  it("quotes empty and unsafe arguments", () => {
    expect(shellQuote("")).toBe("''");
    expect(shellQuote("http://localhost:8000")).toBe("http://localhost:8000");
    expect(shellQuote("http://host:8000?a=1&b=2")).toBe(
      "'http://host:8000?a=1&b=2'",
    );
    expect(shellQuote("$(rm -rf /)")).toBe("'$(rm -rf /)'");
    expect(shellQuote("a'b")).toBe(`'a'"'"'b'`);
  });
  it.each([
    ["/tmp/my notebook.py", "'/tmp/my notebook.py'"],
    [
      String.raw`C:\Users\Jane Doe\notebook.py`,
      String.raw`'C:\Users\Jane Doe\notebook.py'`,
    ],
    [
      String.raw`\\server\share\my notebook.py`,
      String.raw`'\\server\share\my notebook.py'`,
    ],
  ])("quotes path %s as one argument", (path, expected) => {
    expect(shellQuote(path)).toBe(expected);
  });
});

describe("getMarimoCommand", () => {
  afterEach(() => vi.unstubAllEnvs());
  it("uses the checkout command in development", () => {
    vi.stubEnv("DEV", true);
    expect(getMarimoCommand()).toBe("uv run marimo");
  });
  it("uses uvx outside development", () => {
    vi.stubEnv("DEV", false);
    expect(getMarimoCommand()).toBe("uvx marimo@latest");
  });
});

describe("getTerminalCommand", () => {
  it.each([
    ["claude", "claude"],
    ["codex", "codex"],
    ["opencode", "opencode --prompt"],
  ] as const)("launches %s through the public CLI", (agent, cli) => {
    expect(getTerminalCommand(agent, CONNECTION, true, PAIR_CONFIG)).toBe(
      `${cli} "$(uvx marimo@latest pair prompt \\\n  --url http://localhost:8000 \\\n  --notebook nb-one \\\n  --with-token)"`,
    );
  });
  it("uses a stable Session ID for editor execution", () => {
    const command = getTerminalCommand(
      "claude",
      { url: "http://host:8000?a=1&b=2", session: "stable_' {file}" },
      false,
      PAIR_CONFIG,
    );
    expect(command).toContain("--url 'http://host:8000?a=1&b=2'");
    expect(command).toContain(`--session 'stable_'"'"' {file}'`);
    expect(command).not.toContain("--notebook");
  });
  it("prefers the verified Notebook ID to a Session ID", () => {
    const command = getTerminalCommand(
      "codex",
      { ...CONNECTION, session: "stable-one" },
      false,
      PAIR_CONFIG,
    );
    expect(command).toContain("--notebook nb-one");
    expect(command).not.toContain("stable-one");
    expect(command).not.toContain("--with-token");
  });
  it("uses the CLI without injected configuration", () => {
    vi.stubEnv("DEV", true);
    try {
      const command = getTerminalCommand(
        "claude",
        CONNECTION_WITHOUT_TARGET,
        false,
      );
      expect(command).toContain("uv run marimo pair prompt");
      expect(command).not.toMatch(
        /--claude|MARIMO_PAIR_NEXT|--file|--session|--notebook/,
      );
    } finally {
      vi.unstubAllEnvs();
    }
  });
});

describe("getRawPrompt", () => {
  it("does not interpret placeholders in inserted values", () => {
    const prompt = getRawPrompt(
      { url: "http://host/{session}", notebook: "{command}/it's" },
      "tok'en {session} $&",
      {
        ...PAIR_CONFIG,
        command: "custom marimo",
        templates: {
          ...PAIR_CONFIG.templates,
          prompt: "{command}\n{url}\n{notebook}{authentication}",
        },
      },
    );
    expect(prompt).toBe(
      "custom marimo\nhttp://host/{session}\nNotebook: {command}/it's\n" +
        `\n\nFor authenticated notebook discovery, set \`export MARIMO_TOKEN='tok'"'"'en {session} $&'\` in the shell that runs marimo.`,
    );
  });
  it.each([
    [CONNECTION_WITHOUT_TARGET, ""],
    [CONNECTION, "Notebook: nb-one\n"],
    [
      { ...CONNECTION_WITHOUT_TARGET, session: "stable-one" },
      "Session: stable-one\n",
    ],
  ])("renders the shared CLI prompt for %j", (connection, target) => {
    const expected = `Pair with me on this running marimo notebook.\n\nURL: http://localhost:8000\n${target}\nRun \`uvx marimo@latest pair --help\` first.\nUse \`uvx marimo@latest\` for all marimo commands.`;
    expect(getRawPrompt(connection, null, PAIR_CONFIG)).toBe(expected);
    expect(
      getRawPrompt(connection, null, { ...PAIR_CONFIG, hostEnabled: false }),
    ).toBe(expected);
  });
  it("matches the shared prompt without injected templates", () => {
    vi.stubEnv("DEV", false);
    try {
      expect(getRawPrompt(CONNECTION, "secret-token")).toBe(
        getRawPrompt(CONNECTION, "secret-token", PAIR_CONFIG),
      );
    } finally {
      vi.unstubAllEnvs();
    }
  });
});

describe("maskToken", () => {
  it("masks short tokens entirely", () => {
    expect(maskToken("ab")).toBe("****");
    expect(maskToken("abcd")).toBe("****");
  });
  it("reveals only the last four characters", () =>
    expect(maskToken("abcdefgh")).toBe("****efgh"));
  it("caps mask characters at eight", () =>
    expect(maskToken("0123456789abcdef")).toBe("********cdef"));
});
