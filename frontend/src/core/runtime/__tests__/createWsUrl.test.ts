/* Copyright 2024 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import { KnownQueryParams } from "@/core/constants";
import type { SessionId } from "@/core/kernel/session";
import { RuntimeManager } from "../runtime";

describe("RuntimeManager.getWsURL", () => {
  it("should return a URL with the wss protocol when the baseURI uses https", () => {
    const runtime = new RuntimeManager({ url: "https://marimo.app/" });
    const sessionId = "1234" as SessionId;
    const url = runtime.getWsURL(sessionId);
    expect(url.toString()).toBe("wss://marimo.app/ws?session_id=1234");
    expect(url.searchParams.get(KnownQueryParams.sessionId)).toBe(sessionId);
  });

  it("should return a URL with the ws protocol when the baseURI uses http", () => {
    const runtime = new RuntimeManager({ url: "http://marimo.app/" });
    const sessionId = "1234" as SessionId;
    const url = runtime.getWsURL(sessionId);
    expect(url.toString()).toBe("ws://marimo.app/ws?session_id=1234");
    expect(url.searchParams.get(KnownQueryParams.sessionId)).toBe(sessionId);
  });

  it("should work with nested baseURI", () => {
    const runtime = new RuntimeManager({ url: "http://marimo.app/nested/" });
    const sessionId = "1234" as SessionId;
    const url = runtime.getWsURL(sessionId);
    expect(url.toString()).toBe("ws://marimo.app/nested/ws?session_id=1234");
    expect(url.searchParams.get(KnownQueryParams.sessionId)).toBe(sessionId);
  });

  it("should work with nested baseURI and query params", () => {
    const runtime = new RuntimeManager({
      url: "http://marimo.app/nested/?foo=bar",
    });
    window.history.pushState({}, "", "/nested/?file=test.py");
    const sessionId = "1234" as SessionId;
    const url = runtime.getWsURL(sessionId);
    expect(url.toString()).toBe(
      "ws://marimo.app/nested/ws?foo=bar&file=test.py&session_id=1234",
    );
    expect(url.searchParams.get(KnownQueryParams.sessionId)).toBe(sessionId);
  });

  it("should include all query params from current page", () => {
    const runtime = new RuntimeManager({
      url: "http://marimo.app/",
    });
    window.history.pushState({}, "", "/?file=test.py&search=test&other=last");
    const sessionId = "1234" as SessionId;
    const url = runtime.getWsURL(sessionId);
    expect(url.toString()).toBe(
      "ws://marimo.app/ws?file=test.py&search=test&other=last&session_id=1234",
    );
    expect(url.searchParams.get("file")).toBe("test.py");
    expect(url.searchParams.get("search")).toBe("test");
    expect(url.searchParams.get("other")).toBe("last");
    expect(url.searchParams.get(KnownQueryParams.sessionId)).toBe(sessionId);
  });
});
