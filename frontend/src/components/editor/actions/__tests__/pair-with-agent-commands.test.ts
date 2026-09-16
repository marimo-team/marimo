/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import {
  type ConnectionInfo,
  getFileFromURL,
  getMarimoCommand,
  getRawPrompt,
  getTerminalCommand,
  maskToken,
} from "../pair-with-agent-commands";
import type { SessionId } from "@/core/kernel/session";

const CONNECTION: ConnectionInfo = {
  url: "http://localhost:8000",
  sessionId: "s_ab12cd" as SessionId,
  file: "notebooks/example.py",
};

const CONNECTION_WITHOUT_FILE: ConnectionInfo = {
  url: "http://localhost:8000",
  sessionId: "s_ab12cd" as SessionId,
};

describe("getFileFromURL", () => {
  it("returns undefined when the file query parameter is absent or empty", () => {
    expect(getFileFromURL("http://localhost:8000")).toBeUndefined();
    expect(getFileFromURL("http://localhost:8000?file=")).toBeUndefined();
  });

  it("decodes spaces and literal plus signs", () => {
    expect(
      getFileFromURL(
        "http://localhost:8000?file=relative%2Fmy%20notebook%2Bdata.py",
      ),
    ).toBe("relative/my notebook+data.py");
    expect(getFileFromURL("http://localhost:8000?file=my+notebook.py")).toBe(
      "my notebook.py",
    );
  });

  it("preserves decoded Windows paths and uses the first duplicate value", () => {
    expect(
      getFileFromURL(
        "http://localhost:8000?file=C%3A%5CUsers%5CJane%20Doe%5Cnotebook.py",
      ),
    ).toBe(String.raw`C:\Users\Jane Doe\notebook.py`);
    expect(
      getFileFromURL("http://localhost:8000?file=first.py&file=second.py"),
    ).toBe("first.py");
  });
});

describe("getMarimoCommand", () => {
  it("uses the current project environment", () => {
    expect(getMarimoCommand()).toBe("uv run marimo");
  });
});

describe("getTerminalCommand", () => {
  it("includes the url and file for each agent", () => {
    expect(getTerminalCommand("claude", CONNECTION, false)).toBe(
      `claude "$(uv run marimo pair prompt --url http://localhost:8000 --session s_ab12cd --file notebooks/example.py)"`,
    );
    expect(getTerminalCommand("codex", CONNECTION, false)).toBe(
      `codex "$(uv run marimo pair prompt --url http://localhost:8000 --session s_ab12cd --file notebooks/example.py)"`,
    );
    expect(getTerminalCommand("opencode", CONNECTION, false)).toBe(
      `opencode --prompt "$(uv run marimo pair prompt --url http://localhost:8000 --session s_ab12cd --file notebooks/example.py)"`,
    );
  });

  it("omits the file flag when the page URL has no file", () => {
    const command = getTerminalCommand(
      "claude",
      CONNECTION_WITHOUT_FILE,
      false,
    );
    expect(command).not.toContain("--file");
    expect(command).toContain("--session s_ab12cd");
  });

  it("shell-escapes a url containing metacharacters", () => {
    const command = getTerminalCommand(
      "claude",
      {
        url: "http://host:8000?auth=a&b",
        sessionId: CONNECTION.sessionId,
        file: "notebook.py",
      },
      false,
    );
    expect(command).toContain("--url 'http://host:8000?auth=a&b'");
  });

  it.each([
    ["relative/my notebook.py", "--file 'relative/my notebook.py'"],
    ["/tmp/my notebook.py", "--file '/tmp/my notebook.py'"],
    [
      String.raw`C:\Users\Jane Doe\notebook.py`,
      String.raw`--file 'C:\Users\Jane Doe\notebook.py'`,
    ],
    [
      String.raw`\\server\share\my notebook.py`,
      String.raw`--file '\\server\share\my notebook.py'`,
    ],
    ["notebooks/it's.py", `--file 'notebooks/it'"'"'s.py'`],
  ])("shell-escapes file path %s", (file, expected) => {
    const command = getTerminalCommand(
      "claude",
      { url: CONNECTION.url, sessionId: CONNECTION.sessionId, file },
      false,
    );
    expect(command).toContain(expected);
  });

  it("adds --with-token when requested", () => {
    const command = getTerminalCommand("claude", CONNECTION, true);
    expect(command).toContain("--with-token)");
  });

  it("omits --with-token when not requested", () => {
    expect(getTerminalCommand("claude", CONNECTION, false)).not.toContain(
      "--with-token",
    );
  });
});

describe("getRawPrompt", () => {
  it("does not prefix the bootstrap with a launcher", () => {
    const prompt = getRawPrompt(CONNECTION, false);
    expect(prompt).toContain("Start with: marimo pair --help");
    expect(prompt).toContain(
      "If marimo is not on your PATH, run it the same way this notebook server was started.",
    );
    expect(prompt).not.toContain("uvx marimo@latest pair --help");
    expect(prompt).not.toContain("uv run marimo pair --help");
  });

  it("omits file targeting when the page URL has no file", () => {
    const prompt = getRawPrompt(CONNECTION_WITHOUT_FILE, false);
    expect(prompt).toContain("  Session: s_ab12cd");
    expect(prompt).not.toContain("  Notebook:");
  });

  it("matches the unauthenticated CLI prompt shape", () => {
    expect(getRawPrompt(CONNECTION, false)).toMatchInlineSnapshot(`
      "Pair with the live marimo notebook at this target:
        Server: http://localhost:8000
        Session: s_ab12cd
        Notebook: notebooks/example.py

      Start with: marimo pair --help
      If marimo is not on your PATH, run it the same way this notebook server was started.

      Once connected, run \`import marimo as mo; mo.status.toast("Ready to pair")\` to let the user know you are ready."
    `);
  });

  it("directs authenticated users to the token-safe terminal flow", () => {
    expect(getRawPrompt(CONNECTION, true)).toMatchInlineSnapshot(`
      "Pair with the live marimo notebook at this target:
        Server: http://localhost:8000
        Session: s_ab12cd
        Notebook: notebooks/example.py

      Start with: marimo pair --help
      If marimo is not on your PATH, run it the same way this notebook server was started.

      This notebook uses authentication. Run the terminal command with --with-token and paste its output here instead.

      Once connected, run \`import marimo as mo; mo.status.toast("Ready to pair")\` to let the user know you are ready."
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
