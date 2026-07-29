/* Copyright 2026 Marimo. All rights reserved. */

import { afterEach, describe, expect, it, vi } from "vitest";
import {
  type ConnectionInfo,
  getFileFromURL,
  getMarimoCommand,
  getRawPrompt,
  getTerminalCommand,
  maskToken,
  shellQuote,
} from "../pair-with-agent-commands";

const CONNECTION: ConnectionInfo = {
  url: "http://localhost:8000",
  file: "notebooks/example.py",
};

const CONNECTION_WITHOUT_FILE: ConnectionInfo = {
  url: "http://localhost:8000",
};

describe("shellQuote", () => {
  it("quotes an empty string", () => {
    expect(shellQuote("")).toBe("''");
  });

  it("leaves shell-safe values untouched", () => {
    expect(shellQuote("http://localhost:8000")).toBe("http://localhost:8000");
    expect(shellQuote("notebooks/example.py")).toBe("notebooks/example.py");
  });

  it("quotes values with shell metacharacters", () => {
    expect(shellQuote("http://host:8000?a=1&b=2")).toBe(
      "'http://host:8000?a=1&b=2'",
    );
    expect(shellQuote("has space")).toBe("'has space'");
    expect(shellQuote("$(rm -rf /)")).toBe("'$(rm -rf /)'");
  });

  it("escapes embedded single quotes without breaking out", () => {
    // Closes the quote, emits a literal ' via "'", then reopens: '"'"'
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
  ])("quotes non-portable path %s as one argument", (path, expected) => {
    expect(shellQuote(path)).toBe(expected);
  });
});

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
  it("includes the url and file for each agent", () => {
    expect(getTerminalCommand("claude", CONNECTION, false)).toBe(
      `claude "$(uv run marimo pair prompt --url http://localhost:8000 --file notebooks/example.py --claude)"`,
    );
    expect(getTerminalCommand("codex", CONNECTION, false)).toBe(
      `codex "$(uv run marimo pair prompt --url http://localhost:8000 --file notebooks/example.py --codex)"`,
    );
    expect(getTerminalCommand("opencode", CONNECTION, false)).toBe(
      `opencode --prompt "$(uv run marimo pair prompt --url http://localhost:8000 --file notebooks/example.py --opencode)"`,
    );
  });

  it("omits the file flag when the page URL has no file", () => {
    const command = getTerminalCommand(
      "claude",
      CONNECTION_WITHOUT_FILE,
      false,
    );
    expect(command).not.toContain("--file");
    expect(command).not.toContain("--session");
  });

  it("shell-escapes a url containing metacharacters", () => {
    const command = getTerminalCommand(
      "claude",
      { url: "http://host:8000?auth=a&b", file: "notebook.py" },
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
      { url: CONNECTION.url, file },
      false,
    );
    expect(command).toContain(expected);
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
  it("references the file-scoped execute-code command", () => {
    const prompt = getRawPrompt(CONNECTION, null);
    expect(prompt).toContain(
      "execute-code.sh --url http://localhost:8000 --file notebooks/example.py",
    );
    expect(prompt).toContain(
      "Connect to the notebook at: http://localhost:8000 (file notebooks/example.py)",
    );
  });

  it("omits file targeting when the page URL has no file", () => {
    const prompt = getRawPrompt(CONNECTION_WITHOUT_FILE, null);
    expect(prompt).toContain("execute-code.sh --url http://localhost:8000");
    expect(prompt).not.toContain("--file");
    expect(prompt).not.toContain("--session");
  });

  it("omits the token hint when there is no token", () => {
    const prompt = getRawPrompt(CONNECTION, null);
    expect(prompt).not.toContain("--token");
    expect(prompt).not.toContain("auth token");
  });

  it("includes a file-scoped token hint when a token is present", () => {
    const prompt = getRawPrompt(CONNECTION, "secret-token");
    expect(prompt).toContain(
      "execute-code.sh --url http://localhost:8000 --file notebooks/example.py --token secret-token",
    );
  });

  it("shell-escapes a token containing a single quote", () => {
    const prompt = getRawPrompt(CONNECTION, "tok'en");
    expect(prompt).toContain(`--token 'tok'"'"'en'`);
  });

  it("matches the CLI prompt shape", () => {
    const prompt = getRawPrompt(CONNECTION, null);
    expect(prompt).toMatchInlineSnapshot(`
      "Use the /marimo-pair skill to pair-program on a running marimo notebook.

      Connect to the notebook at: http://localhost:8000 (file notebooks/example.py)

      Use \`execute-code.sh --url http://localhost:8000 --file notebooks/example.py\` from the marimo-pair skill to execute code in the notebook.

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
