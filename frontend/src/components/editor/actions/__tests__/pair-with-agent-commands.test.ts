/* Copyright 2026 Marimo. All rights reserved. */

import { afterEach, describe, expect, it, vi } from "vitest";
import {
  type ConnectionInfo,
  getMarimoCommand,
  getRawPrompt,
  getTerminalCommand,
  maskToken,
} from "../pair-with-agent-commands";

const CONNECTION: ConnectionInfo = {
  url: "http://localhost:8000",
  sessionId: "s_ab12cd",
};

describe("getMarimoCommand", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("uses the local checkout in dev", () => {
    vi.stubEnv("DEV", true);
    expect(getMarimoCommand()).toBe("uv run marimo");
  });

  it("uses uvx outside of dev", () => {
    vi.stubEnv("DEV", false);
    expect(getMarimoCommand()).toBe("uvx marimo@latest");
  });
});

describe("getTerminalCommand", () => {
  it("includes the url and session for each agent", () => {
    expect(getTerminalCommand("claude", CONNECTION, false)).toBe(
      `claude "$(uv run marimo pair prompt --url 'http://localhost:8000' --session 's_ab12cd' --claude)"`,
    );
    expect(getTerminalCommand("codex", CONNECTION, false)).toBe(
      `codex "$(uv run marimo pair prompt --url 'http://localhost:8000' --session 's_ab12cd' --codex)"`,
    );
    expect(getTerminalCommand("opencode", CONNECTION, false)).toBe(
      `opencode --prompt "$(uv run marimo pair prompt --url 'http://localhost:8000' --session 's_ab12cd' --opencode)"`,
    );
  });

  it("always targets the given session, not a random one", () => {
    const command = getTerminalCommand("claude", CONNECTION, false);
    expect(command).toContain("--session 's_ab12cd'");
  });

  it("adds --with-token before the agent flag when requested", () => {
    const command = getTerminalCommand("claude", CONNECTION, true);
    expect(command).toContain("--with-token --claude");
  });

  it("omits --with-token when not requested", () => {
    expect(getTerminalCommand("claude", CONNECTION, false)).not.toContain(
      "--with-token",
    );
  });
});

describe("getRawPrompt", () => {
  it("references the session-scoped execute-code command", () => {
    const prompt = getRawPrompt(CONNECTION, null);
    expect(prompt).toContain(
      "execute-code.sh --url http://localhost:8000 --session s_ab12cd",
    );
    expect(prompt).toContain(
      "Connect to the notebook at: http://localhost:8000 (session s_ab12cd)",
    );
  });

  it("omits the token hint when there is no token", () => {
    const prompt = getRawPrompt(CONNECTION, null);
    expect(prompt).not.toContain("--token");
    expect(prompt).not.toContain("auth token");
  });

  it("includes a session-scoped token hint when a token is present", () => {
    const prompt = getRawPrompt(CONNECTION, "secret-token");
    expect(prompt).toContain(
      "execute-code.sh --url http://localhost:8000 --session s_ab12cd --token 'secret-token'",
    );
  });

  it("matches the CLI prompt shape", () => {
    const prompt = getRawPrompt(CONNECTION, null);
    expect(prompt).toMatchInlineSnapshot(`
      "Use the /marimo-pair skill to pair-program on a running marimo notebook.

      Connect to the notebook at: http://localhost:8000 (session s_ab12cd)

      Use \`execute-code.sh --url http://localhost:8000 --session s_ab12cd\` from the marimo-pair skill to execute code in the notebook.

      Once you are connected, send a fun toast (mo.status.toast(...)) to the user inside marimo letting them know you're ready to pair."
    `);
  });
});

describe("maskToken", () => {
  it("masks short tokens entirely", () => {
    expect(maskToken("ab")).toBe("****");
    expect(maskToken("abcd")).toBe("****");
  });

  it("reveals only the last four characters", () => {
    expect(maskToken("abcdefgh")).toBe("****efgh");
  });

  it("caps the number of mask characters at eight", () => {
    expect(maskToken("0123456789abcdef")).toBe("********cdef");
  });
});
