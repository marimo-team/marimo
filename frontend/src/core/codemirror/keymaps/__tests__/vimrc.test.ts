/* Copyright 2024 Marimo. All rights reserved. */
import { describe, expect, it, vi } from "vitest";
import { parseVimrc } from "../vimrc";
// @ts-expect-error: no declaration file
import dedent from "string-dedent";

describe("parseVimrc", () => {
  it("should parse mappings with no mode", () => {
    const content = `
      " This is a comment
      map j gj
      noremap k gk
      unmap k
      mapclear
    `;

    const err = vi.fn();
    const mappings = parseVimrc(dedent(content), err);
    expect(mappings).toEqual([
      { name: "map", args: { lhs: "j", rhs: "gj" } },
      { name: "noremap", args: { lhs: "k", rhs: "gk" } },
      { name: "unmap", args: { lhs: "k" } },
      { name: "mapclear" },
    ]);
    expect(err.mock.calls.length).toEqual(0);
  });

  it("should parse normal mode mappings", () => {
    const content = `
      nmap j gj
      nnoremap k gk
      nunmap k
      nmapclear
    `;

    const err = vi.fn();
    const mappings = parseVimrc(dedent(content), err);
    expect(mappings).toEqual([
      { name: "nmap", args: { lhs: "j", rhs: "gj" }, mode: "normal" },
      { name: "nnoremap", args: { lhs: "k", rhs: "gk" }, mode: "normal" },
      { name: "nunmap", args: { lhs: "k" }, mode: "normal" },
      { name: "nmapclear", mode: "normal" },
    ]);
    expect(err.mock.calls.length).toEqual(0);
  });

  it("should parse insert mode mappings", () => {
    const content = `
      imap jj <Esc>
      inoremap jk <Esc>
      iunmap jj
      imapclear
    `;

    const err = vi.fn();
    const mappings = parseVimrc(dedent(content), err);
    expect(mappings).toEqual([
      { name: "imap", args: { lhs: "jj", rhs: "<Esc>" }, mode: "insert" },
      { name: "inoremap", args: { lhs: "jk", rhs: "<Esc>" }, mode: "insert" },
      { name: "iunmap", args: { lhs: "jj" }, mode: "insert" },
      { name: "imapclear", mode: "insert" },
    ]);
    expect(err.mock.calls.length).toEqual(0);
  });

  // because " is a valid key
  it("should handle quotes as keys", () => {
    const content = `
      map "j "0p
      unmap "j
    `;

    const err = vi.fn();
    const mappings = parseVimrc(dedent(content), err);
    expect(mappings).toEqual([
      { name: "map", args: { lhs: '"j', rhs: '"0p' } },
      { name: "unmap", args: { lhs: '"j' } },
    ]);
    expect(err.mock.calls.length).toEqual(0);
  });

  it("should skip invalid mappings", () => {
    const content = `
      map
      map j
      unmap k j
      mapclear arg
    `;

    const err = vi.fn();
    const mappings = parseVimrc(dedent(content), err);
    expect(mappings).toEqual([
      { name: "unmap", args: { lhs: "k" } },
      // Ideally mapclear should not appear here
      { name: "mapclear" },
      // The vim behavior lhs = "l j", is not achievable with the current regexp split
      // { name: "unmap", args: { lhs: "k j" } },
    ]);
    expect(err.mock.calls.length).toEqual(2);
  });

  it("should handle empty content", () => {
    const content = "";
    const err = vi.fn();
    const mappings = parseVimrc(content, err);
    expect(mappings).toEqual([]);
    expect(err.mock.calls.length).toEqual(0);
  });

  it("should handle only comments", () => {
    const content = `
      " This is a comment
      " Another comment
    `;

    const err = vi.fn();
    const mappings = parseVimrc(dedent(content), err);
    expect(mappings).toEqual([]);
    expect(err.mock.calls.length).toEqual(0);
  });
});
