/* Copyright 2024 Marimo. All rights reserved. */

import type { EditorView, PluginValue } from "@codemirror/view";

let lastFocusedEditorRef: WeakRef<EditorView> | null = null;

/** Options for {@linkcode VimCursorVisibilityPlugin}. */
interface VimCursorVisibilityPluginOptions {
  /** The editor view to manage Vim cursor visibility. */
  view: EditorView;
}

/**
 * A CodeMirror plugin that manages vim cursor visibility.
 *
 * Ensures that the vim cursor (block cursor in normal mode) is only
 * visible in the last focused editor. All other editors will have
 * their vim cursors hidden entirely, preventing multiple cursors
 * from appearing across all cells when vim mode is enabled.
 */
export class VimCursorVisibilityPlugin implements PluginValue {
  private view: EditorView;
  private abortController = new AbortController();

  constructor(options: VimCursorVisibilityPluginOptions) {
    this.view = options.view;
    this.view.dom.addEventListener(
      "focus",
      () => {
        lastFocusedEditorRef = new WeakRef(this.view);
      },
      {
        signal: this.abortController.signal,
        capture: true,
      },
    );
    this.update();
  }

  update() {
    const vimCursorLayer = this.view.dom.querySelector(".cm-vimCursorLayer");
    if (vimCursorLayer instanceof HTMLElement) {
      const isLastFocused = lastFocusedEditorRef?.deref() === this.view;
      vimCursorLayer.style.display = isLastFocused ? "" : "none";
    }
  }

  destroy(): void {
    this.abortController.abort();
  }
}
