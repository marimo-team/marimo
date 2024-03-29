/* Copyright 2024 Marimo. All rights reserved. */
import { switchLanguage } from "@/core/codemirror/language/extension";
import { EditorView } from "@codemirror/view";
import React from "react";
import { MarkdownIcon, PythonIcon } from "./icons";
import { Button } from "@/components/ui/button";
import { Tooltip } from "@/components/ui/tooltip";
import { startCase } from "lodash-es";
import { LanguageAdapter } from "@/core/codemirror/language/types";

interface Props {
  editorView: EditorView;
  canUseMarkdown: boolean;
  languageAdapter: LanguageAdapter["type"] | undefined;
}

export const LanguageToggle: React.FC<Props> = ({
  editorView,
  languageAdapter,
  canUseMarkdown,
}) => {
  if (!canUseMarkdown && languageAdapter !== "markdown") {
    return null;
  }

  const otherLanguage = languageAdapter === "markdown" ? "python" : "markdown";
  const Icon = languageAdapter === "markdown" ? PythonIcon : MarkdownIcon;

  return (
    <div className="absolute top-0 right-5 z-20 hover-action">
      <Tooltip content={`View as ${startCase(otherLanguage)}`}>
        <Button
          data-testid="language-toggle-button"
          variant="text"
          size="xs"
          className="opacity-80"
        >
          <Icon
            className="cursor-pointer"
            fill={"var(--sky-11)"}
            fontSize={20}
            onClick={() => {
              switchLanguage(editorView, otherLanguage);
            }}
          />
        </Button>
      </Tooltip>
    </div>
  );
};
