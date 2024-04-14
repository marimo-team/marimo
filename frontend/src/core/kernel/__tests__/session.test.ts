/* Copyright 2024 Marimo. All rights reserved. */
import { describe, expect, it } from "vitest";
import { generateSessionId, isSessionId } from "../session";

describe("Session", () => {
  it("should create a session", () => {
    const id = generateSessionId();
    expect(isSessionId(id)).toBe(true);
  });
});
