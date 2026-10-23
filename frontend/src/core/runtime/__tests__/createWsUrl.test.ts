/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import { KnownQueryParams } from "@/core/constants";
import type { SessionId } from "@/core/kernel/session";
import { RuntimeManager } from "../runtime";

describe("RuntimeManager.getWsURL", () => {
  it("should return a URL with the wss protocol when the baseURI uses https", () => {
    const runtime = new RuntimeManager({
      url: "https://marimo.app/",
      lazy: true,
    });
    const sessionId = "1234" as SessionId;
    const url = runtime.getWsURL(sessionId);
    expect(url.toString()).toBe(
      "wss://marimo.app/ws?query_params=&session_id=1234",
    );
    expect(url.searchParams.get(KnownQueryParams.sessionId)).toBe(sessionId);
  });

  it("should return a URL with the ws protocol when the baseURI uses http", () => {
    const runtime = new RuntimeManager({
      url: "http://marimo.app/",
      lazy: true,
    });
    const sessionId = "1234" as SessionId;
    const url = runtime.getWsURL(sessionId);
    expect(url.toString()).toBe(
      "ws://marimo.app/ws?query_params=&session_id=1234",
    );
    expect(url.searchParams.get(KnownQueryParams.sessionId)).toBe(sessionId);
  });

  it("should work with nested baseURI", () => {
    const runtime = new RuntimeManager({
      url: "http://marimo.app/nested/",
      lazy: true,
    });
    const sessionId = "1234" as SessionId;
    const url = runtime.getWsURL(sessionId);
    expect(url.toString()).toBe(
      "ws://marimo.app/nested/ws?query_params=&session_id=1234",
    );
    expect(url.searchParams.get(KnownQueryParams.sessionId)).toBe(sessionId);
  });

  it("should work with nested baseURI and query params", () => {
    const runtime = new RuntimeManager({
      url: "http://marimo.app/nested/?foo=bar",
      lazy: true,
    });
    window.history.pushState({}, "", "/nested/?file=test.py");
    const sessionId = "1234" as SessionId;
    const url = runtime.getWsURL(sessionId);
    expect(url.toString()).toBe(
      "ws://marimo.app/nested/ws?foo=bar&file=test.py&query_params=foo%3Dbar%26file%3Dtest.py&session_id=1234",
    );
    expect(url.searchParams.get(KnownQueryParams.sessionId)).toBe(sessionId);
  });

  it("should include all query params from current page", () => {
    const runtime = new RuntimeManager({
      url: "http://marimo.app/",
      lazy: true,
    });
    window.history.pushState({}, "", "/?file=test.py&search=test&other=last");
    const sessionId = "1234" as SessionId;
    const url = runtime.getWsURL(sessionId);
    expect(url.toString()).toBe(
      "ws://marimo.app/ws?file=test.py&query_params=file%3Dtest.py%26search%3Dtest%26other%3Dlast&session_id=1234",
    );
    expect(url.searchParams.get("file")).toBe("test.py");
    expect(url.searchParams.get("query_params")).toBe(
      "file=test.py&search=test&other=last",
    );
    expect(url.searchParams.get(KnownQueryParams.sessionId)).toBe(sessionId);
  });
});

describe.each(["getWsURL", "getSseURL"] as const)(
  "RuntimeManager.%s",
  (method) => {
    it("preserves runtime parameters and repeated page values", () => {
      window.history.pushState({}, "", "/?tag=page-one&tag=page-two");
      const runtime = new RuntimeManager(
        {
          url: `${window.location.origin}/nested?proxy_token=secret&tag=base&base=one&base=two`,
          lazy: true,
        },
        true,
      );
      const url = runtime[method]("session" as SessionId);
      expect([...url.searchParams]).toEqual([
        ["proxy_token", "secret"],
        ["tag", "base"],
        ["base", "one"],
        ["base", "two"],
        [
          "query_params",
          "proxy_token=secret&base=one&base=two&tag=page-one&tag=page-two",
        ],
        ["session_id", "session"],
      ]);
    });

    it("keeps notebook parameters out of the stream options", () => {
      const notebookParams = new URLSearchParams([
        ["types", "scatter"],
        ["cursor", "page-2"],
        ["run_id", "experiment"],
        ["query_params", "nested=value&other=1"],
        ["tag", "one"],
        ["tag", "two"],
        ["empty", ""],
        ["text", "a+b & café"],
        ["file", "test.py"],
        ["kiosk", "true"],
      ]);
      window.history.pushState(
        {},
        "",
        `/?${notebookParams}&session_id=page-session`,
      );
      const runtime = new RuntimeManager(
        { url: window.location.origin, lazy: true },
        true,
      );
      const url = runtime[method]("actual-session" as SessionId);

      expect(Object.fromEntries(url.searchParams)).toEqual({
        file: "test.py",
        kiosk: "true",
        session_id: "actual-session",
        query_params: notebookParams.toString(),
      });
      expect([
        ...new URLSearchParams(url.searchParams.get("query_params") ?? ""),
      ]).toEqual([...notebookParams]);
    });
  },
);
