/* Copyright 2026 Marimo. All rights reserved. */

import type { EditorState } from "@codemirror/state";
import type { EditorView } from "@codemirror/view";
import { dequal } from "dequal";
import { getCellCode } from "./cell-code";
import { languageAdapterFromCode, languageAdapterState } from "./extension";
import { languageMetadataField } from "./metadata";
import type { LanguageAdapterType } from "./types";

/**
 * Get the editor code as Python
 * Handles when the editor has a different language adapter
 */
export function getEditorCodeAsPython(
  editor: { state: EditorState },
  fromPos?: number,
  toPos?: number,
): string {
  if (fromPos === undefined) {
    return getCellCode(editor.state);
  }
  const languageAdapter = editor.state.field(languageAdapterState);
  const metadata = editor.state.field(languageMetadataField);
  const editorText = editor.state.doc.toString();
  return languageAdapter.transformOut(
    editorText.slice(fromPos, toPos),
    metadata,
  )[0];
}

/**
 * Split the editor code into two parts at the cursor position
 */
export function splitEditor(editor: EditorView) {
  const cursorPos = editor.state.selection.main.head;
  const editorCode = editor.state.doc.toString();

  const isCursorAtLineStart =
    editorCode.length > 0 && editorCode[cursorPos - 1] === "\n";
  const isCursorAtLineEnd =
    editorCode.length > 0 && editorCode[cursorPos] === "\n";

  const beforeAdjustedCursorPos = isCursorAtLineStart
    ? cursorPos - 1
    : cursorPos;
  const afterAdjustedCursorPos = isCursorAtLineEnd ? cursorPos + 1 : cursorPos;

  const beforeCursorCode = getEditorCodeAsPython(
    editor,
    0,
    beforeAdjustedCursorPos,
  );
  const afterCursorCode = getEditorCodeAsPython(editor, afterAdjustedCursorPos);

  return {
    beforeCursorCode,
    afterCursorCode,
  };
}

/** Join two cells' code; null for mixed languages or settings, or SQL. */
export function mergeCellCode(above: string, below: string): string | null {
  if (!below.trim()) {
    return above;
  }
  if (!above.trim()) {
    return below;
  }
  const adapter = languageAdapterFromCode(above);
  if (adapter.type === "sql" || languageAdapterFromCode(below) !== adapter) {
    return null;
  }
  const [aboveText, , metadata] = adapter.transformIn(above);
  const [belowText, , belowMetadata] = adapter.transformIn(below);
  if (!dequal(metadata, belowMetadata)) {
    return null;
  }
  return adapter.transformOut(
    `${aboveText}${separatorFor(adapter.type)}${belowText}`,
    metadata,
  )[0];
}

/** The code above a merge, if `merged` still ends with the code below. */
export function unmergeCellCode(merged: string, below: string): string | null {
  if (!below.trim()) {
    return merged;
  }
  const adapter = languageAdapterFromCode(merged);
  const [mergedText, , metadata] = adapter.transformIn(merged);
  const text = mergedText.trimEnd();
  const belowText = adapter.transformIn(below)[0].trimEnd();
  if (text === belowText) {
    return "";
  }
  const suffix = `${separatorFor(adapter.type)}${belowText}`;
  if (!text.endsWith(suffix)) {
    return null;
  }
  return adapter.transformOut(text.slice(0, -suffix.length), metadata)[0];
}

// Markdown needs a blank line, or the two paragraphs run together.
const separatorFor = (type: LanguageAdapterType) =>
  type === "markdown" ? "\n\n" : "\n";
