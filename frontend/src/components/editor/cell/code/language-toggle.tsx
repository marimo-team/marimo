/* Copyright 2024 Marimo. All rights reserved. */
import {
  languageAdapterState,
  switchLanguage,
} from "@/core/codemirror/language/extension";
import { EditorView } from "@codemirror/view";
import React, { useState } from "react";
import { MarkdownIcon, PythonIcon } from "./icons";
import { Button } from "@/components/ui/button";
import { Tooltip } from "@/components/ui/tooltip";
import { startCase } from "lodash-es";

interface Props {
  editorView: EditorView;
  canUseMarkdown: boolean;
}

export const LanguageToggle: React.FC<Props> = ({
  editorView,
  canUseMarkdown,
}) => {
  const [languageAdapter, setLanguageAdapter] = useState(
    editorView.state.field(languageAdapterState).type,
  );

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
              setLanguageAdapter(otherLanguage);
              switchLanguage(editorView, otherLanguage);
            }}
          />
        </Button>
      </Tooltip>
    </div>
  );
};
