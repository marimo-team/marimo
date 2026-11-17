/* Copyright 2026 Marimo. All rights reserved. */

import { EditorState } from "@codemirror/state";
import { EditorView } from "@codemirror/view";
import { fireEvent, render, screen } from "@testing-library/react";
import { createRef } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { TooltipProvider } from "@/components/ui/tooltip";
import { switchLanguage } from "@/core/codemirror/language/extension";
import { LanguageToggle, LanguageToggles } from "../language-toggle";

vi.mock("@/core/codemirror/language/extension", () => ({
  switchLanguage: vi.fn(),
}));

describe("LanguageToggle", () => {
  afterEach(() => {
    vi.mocked(switchLanguage).mockClear();
  });

  it("uses the editor mounted after the button rendered", () => {
    const editorViewRef = createRef<EditorView>();
    const onAfterToggle = vi.fn();
    render(
      <TooltipProvider>
        <LanguageToggle
          editorViewRef={editorViewRef}
          currentLanguageAdapter="python"
          canSwitchToLanguage={true}
          toType="markdown"
          displayName="Markdown"
          icon="Markdown"
          onAfterToggle={onAfterToggle}
        />
      </TooltipProvider>,
    );

    fireEvent.click(screen.getByRole("button", { name: "Markdown" }));
    expect(switchLanguage).not.toHaveBeenCalled();
    expect(onAfterToggle).not.toHaveBeenCalled();

    const view = new EditorView({ state: EditorState.create() });
    editorViewRef.current = view;
    try {
      fireEvent.click(screen.getByRole("button", { name: "Markdown" }));
      expect(switchLanguage).toHaveBeenCalledWith(view, {
        language: "markdown",
      });
      expect(onAfterToggle).toHaveBeenCalledOnce();
    } finally {
      view.destroy();
    }
  });

  it("uses the correct callback for each language toggle", () => {
    const view = new EditorView({ state: EditorState.create() });
    const editorViewRef = createRef<EditorView>();
    editorViewRef.current = view;

    const onAfterToggleSQL = vi.fn();
    const onAfterToggleMarkdown = vi.fn();

    try {
      render(
        <TooltipProvider>
          <LanguageToggles
            editorViewRef={editorViewRef}
            code=""
            currentLanguageAdapter="python"
            onAfterToggleSQL={onAfterToggleSQL}
            onAfterToggleMarkdown={onAfterToggleMarkdown}
          />
        </TooltipProvider>,
      );

      const toggleButtons = screen.getAllByTestId("language-toggle-button");

      fireEvent.click(toggleButtons[0]);

      expect(onAfterToggleSQL).toHaveBeenCalledOnce();
      expect(onAfterToggleMarkdown).not.toHaveBeenCalled();

      fireEvent.click(toggleButtons[1]);

      expect(onAfterToggleMarkdown).toHaveBeenCalledOnce();
      expect(onAfterToggleSQL).toHaveBeenCalledOnce();
    } finally {
      view.destroy();
    }
  });
});
