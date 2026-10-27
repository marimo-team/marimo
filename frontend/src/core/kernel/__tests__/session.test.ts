/* Copyright 2026 Marimo. All rights reserved. */
import { afterEach, describe, expect, it, vi } from "vitest";
import type { AppMode } from "@/core/mode";
import { generateSessionId, isSessionId } from "../session";

const URL_SESSION_ID = "s_abc123";

/**
 * Load a fresh copy of the session module against the given URL and mode.
 * The module caches its session id, so each case needs its own instance.
 */
async function loadSession(opts: { mode: AppMode | undefined; url: string }) {
  vi.resetModules();
  window.history.replaceState({}, "", opts.url);
  const { store } = await import("@/core/state/jotai");
  const { initialModeAtom } = await import("@/core/mode");
  store.set(initialModeAtom, opts.mode);
  return await import("../session");
}

function currentSearchParams(): URLSearchParams {
  return new URL(window.location.href).searchParams;
}

describe("Session", () => {
  afterEach(() => {
    window.history.replaceState({}, "", "/");
  });

  it("should create a session", () => {
    const id = generateSessionId();
    expect(isSessionId(id)).toBe(true);
  });

  it("resumes the session named in the URL in edit mode", async () => {
    const { getSessionId } = await loadSession({
      mode: "edit",
      url: `/?session_id=${URL_SESSION_ID}`,
    });
    expect(getSessionId()).toBe(URL_SESSION_ID);
    expect(currentSearchParams().has("session_id")).toBe(false);
  });

  it("keeps the URL session id in kiosk mode so a refresh resumes it", async () => {
    const { getSessionId } = await loadSession({
      mode: "edit",
      url: `/?kiosk=true&session_id=${URL_SESSION_ID}`,
    });
    expect(getSessionId()).toBe(URL_SESSION_ID);
    expect(currentSearchParams().get("session_id")).toBe(URL_SESSION_ID);
    expect(currentSearchParams().get("kiosk")).toBe("true");
  });

  it("keeps the kiosk flag in edit mode when the URL names no session", async () => {
    const { getSessionId } = await loadSession({
      mode: "edit",
      url: "/?kiosk=true",
    });
    expect(isSessionId(getSessionId())).toBe(true);
    expect(currentSearchParams().get("kiosk")).toBe("true");
  });

  it("starts a new session when the URL session id is malformed", async () => {
    const { getSessionId } = await loadSession({
      mode: "edit",
      url: "/?session_id=not-a-session",
    });
    const id = getSessionId();
    expect(isSessionId(id)).toBe(true);
    expect(id).not.toBe("not-a-session");
  });

  it("ignores the URL session id in read mode", async () => {
    const { getSessionId } = await loadSession({
      mode: "read",
      url: `/?session_id=${URL_SESSION_ID}`,
    });
    const id = getSessionId();
    expect(isSessionId(id)).toBe(true);
    expect(id).not.toBe(URL_SESSION_ID);
    // The param is still scrubbed so a refresh cannot reintroduce it.
    expect(currentSearchParams().has("session_id")).toBe(false);
  });

  it("drops both the session id and the kiosk flag in read mode", async () => {
    const { getSessionId } = await loadSession({
      mode: "read",
      url: `/?kiosk=true&session_id=${URL_SESSION_ID}`,
    });
    expect(getSessionId()).not.toBe(URL_SESSION_ID);
    expect(currentSearchParams().has("session_id")).toBe(false);
    // The kiosk flag is forwarded to the websocket URL, and the server
    // refuses kiosk connections to an app, so it must not survive here.
    expect(currentSearchParams().has("kiosk")).toBe(false);
  });

  it("drops a lone kiosk flag in read mode", async () => {
    const { getSessionId } = await loadSession({
      mode: "read",
      url: "/?kiosk=true",
    });
    expect(isSessionId(getSessionId())).toBe(true);
    expect(currentSearchParams().has("kiosk")).toBe(false);
  });

  it("ignores the URL session id when the mode is not yet known", async () => {
    const { getSessionId } = await loadSession({
      mode: undefined,
      url: `/?session_id=${URL_SESSION_ID}`,
    });
    expect(getSessionId()).not.toBe(URL_SESSION_ID);
    expect(currentSearchParams().has("session_id")).toBe(false);
  });

  it("returns the same id on every call", async () => {
    const { getSessionId } = await loadSession({ mode: "read", url: "/" });
    expect(getSessionId()).toBe(getSessionId());
  });
});
