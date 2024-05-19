/* Copyright 2024 Marimo. All rights reserved. */
import { Extension, Prec } from "@codemirror/state";
import {
  insertBlockquote,
  insertBoldMarker,
  insertCodeMarker,
  insertItalicMarker,
  insertLink,
  insertOL,
  insertUL,
} from "./commands";
import { EditorView, keymap } from "@codemirror/view";
import { HOTKEYS } from "@/core/hotkeys/hotkeys";

export function enhancedMarkdownExtension(): Extension[] {
  return [
    Prec.highest(
      keymap.of([
        // Runs always
        {
          key: HOTKEYS.getHotkey("markdown.bold").key,
          stopPropagation: true,
          run: insertBoldMarker,
        },
        // Runs always
        {
          key: HOTKEYS.getHotkey("markdown.italic").key,
          stopPropagation: true,
          run: insertItalicMarker,
        },
        // Only runs on selection
        {
          key: HOTKEYS.getHotkey("markdown.link").key,
          stopPropagation: true,
          run: (cm) => insertLink(cm),
        },
        // Only runs on selection
        {
          key: HOTKEYS.getHotkey("markdown.orderedList").key,
          run: insertOL,
        },
        // Only runs on selection
        {
          key: HOTKEYS.getHotkey("markdown.unorderedList").key,
          run: insertUL,
        },
        // Only runs on selection
        {
          key: HOTKEYS.getHotkey("markdown.blockquote").key,
          run: insertBlockquote,
        },
        // Only runs on selection
        {
          key: HOTKEYS.getHotkey("markdown.code").key,
          run: insertCodeMarker,
        },
        // Only runs on selection
        {
          key: "`",
          run: insertCodeMarker,
        },
      ]),
    ),
    // Smart on paste of URLs
    EditorView.domEventHandlers({
      paste: (event, view) => {
        // If no selection, do nothing
        if (view.state.selection.main.empty) {
          return;
        }

        const url = event.clipboardData?.getData("text/plain");
        if (url?.startsWith("http")) {
          event.preventDefault();
          insertLink(view, url);
        }
      },
    }),
  ];
}
