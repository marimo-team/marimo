/* Copyright 2024 Marimo. All rights reserved. */
import { describe, expect, it } from "vitest";
import { parseVimrc } from "../vim";
// @ts-expect-error: no declaration file
import dedent from "string-dedent";

describe("parseVimrc", () => {
  it("should parse normal mode mappings", () => {
    const content = `
      " This is a comment
      map j gj
      nmap k gk
    `;

    const mappings = parseVimrc(dedent(content));
    expect(mappings).toEqual([
      { key: "j", action: "gj", context: "normal" },
      { key: "k", action: "gk", context: "normal" },
    ]);
  });

  it("should parse insert mode mappings", () => {
    const content = `
      imap jj <Esc>
      imap jk <Esc>
    `;

    const mappings = parseVimrc(dedent(content));
    expect(mappings).toEqual([
      { key: "jj", action: "<Esc>", context: "insert" },
      { key: "jk", action: "<Esc>", context: "insert" },
    ]);
  });

  it("should handle quoted keys and actions", () => {
    const content = `
      map "j" "gj"
      imap "jj" "<Esc>"
    `;

    const mappings = parseVimrc(dedent(content));
    expect(mappings).toEqual([
      { key: "j", action: "gj", context: "normal" },
      { key: "jj", action: "<Esc>", context: "insert" },
    ]);
  });

  it("should skip invalid mappings", () => {
    const content = `
      map
      map j
      map k
    `;

    const mappings = parseVimrc(dedent(content));
    expect(mappings).toEqual([]);
  });

  it("should handle empty content", () => {
    const content = "";
    const mappings = parseVimrc(content);
    expect(mappings).toEqual([]);
  });

  it("should handle only comments", () => {
    const content = `
      " This is a comment
      " Another comment
    `;

    const mappings = parseVimrc(dedent(content));
    expect(mappings).toEqual([]);
  });
});
