/* Copyright 2026 Marimo. All rights reserved. */
import { completionStatus } from "@codemirror/autocomplete";
import type { EditorView } from "@codemirror/view";
import { type CodeMirror, getCM } from "@replit/codemirror-vim";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { editorWillConsumeEscape } from "../utils";

vi.mock("@codemirror/autocomplete", () => ({
  completionStatus: vi.fn(() => null),
}));
vi.mock("@marimo-team/codemirror-languageserver", () => ({
  signatureHelpTooltipField: { sentinel: "signatureHelpTooltipField" },
}));
vi.mock("@replit/codemirror-vim", () => ({
  getCM: vi.fn(() => null),
}));

interface FakeViewOptions {
  ranges?: Array<{ empty: boolean }>;
  signatureHelp?: unknown;
}

function fakeView({
  ranges = [{ empty: true }],
  signatureHelp = null,
}: FakeViewOptions = {}): EditorView {
  return {
    state: {
      selection: { ranges },
      field: vi.fn(() => signatureHelp),
    },
  } as unknown as EditorView;
}

function mockVimInsertMode(insertMode: boolean) {
  vi.mocked(getCM).mockReturnValue({
    state: { vim: { insertMode } },
  } as unknown as CodeMirror);
}

describe("editorWillConsumeEscape", () => {
  beforeEach(() => {
    vi.mocked(completionStatus).mockReturnValue(null);
    vi.mocked(getCM).mockReturnValue(null);
  });

  it("returns false when idle: no popups, empty selection, not Vim insert", () => {
    expect(editorWillConsumeEscape(fakeView())).toBe(false);
  });

  it("returns true in Vim insert mode", () => {
    mockVimInsertMode(true);
    expect(editorWillConsumeEscape(fakeView())).toBe(true);
  });

  it("returns false in Vim normal mode (insert mode off)", () => {
    mockVimInsertMode(false);
    expect(editorWillConsumeEscape(fakeView())).toBe(false);
  });

  it("returns true when an autocomplete popup is open", () => {
    vi.mocked(completionStatus).mockReturnValue("active");
    expect(editorWillConsumeEscape(fakeView())).toBe(true);
  });

  it("returns true when a signature-help popup is open", () => {
    expect(
      editorWillConsumeEscape(fakeView({ signatureHelp: { pos: 0 } })),
    ).toBe(true);
  });

  it("returns true when any selection range is non-empty", () => {
    expect(
      editorWillConsumeEscape(
        fakeView({ ranges: [{ empty: true }, { empty: false }] }),
      ),
    ).toBe(true);
  });
});
