/* Copyright 2026 Marimo. All rights reserved. */
import { describe, expect, it } from "vitest";
import { smartMatch, smartMatchFilter } from "../smartMatch";

describe("smartMatch", () => {
  it("matches exact word", () => {
    expect(smartMatch("run", "Run cell")).toBe(true);
  });

  it("matches word prefix", () => {
    expect(smartMatch("exe", "execute start")).toBe(true);
  });

  it("matches across array of haystacks", () => {
    expect(smartMatch("exe", ["Run", "execute start"])).toBe(true);
  });

  it("does not match unrelated terms", () => {
    expect(smartMatch("xyz", "Run cell")).toBe(false);
  });

  it("empty search matches everything", () => {
    expect(smartMatch("", "anything")).toBe(true);
  });

  it("multi-word needle requires all words to match", () => {
    expect(smartMatch("run cell", "Run cell")).toBe(true);
    expect(smartMatch("run xyz", "Run cell")).toBe(false);
  });

  it("is case-insensitive", () => {
    expect(smartMatch("RUN", "run cell")).toBe(true);
  });

  it("skips null/undefined haystacks", () => {
    expect(smartMatch("run", [null, undefined, "Run cell"])).toBe(true);
    expect(smartMatch("run", [null, undefined])).toBe(false);
  });
});

describe("smartMatchFilter", () => {
  it("returns 1 for match", () => {
    expect(smartMatchFilter("Run cell", "run")).toBe(1);
  });

  it("returns 0 for no match", () => {
    expect(smartMatchFilter("Run cell", "xyz")).toBe(0);
  });

  it("matches against keywords", () => {
    expect(smartMatchFilter("Run", "execute", ["execute", "start"])).toBe(1);
  });

  it("does not match without relevant keywords", () => {
    expect(smartMatchFilter("Run", "preferences", ["execute"])).toBe(0);
  });
});
