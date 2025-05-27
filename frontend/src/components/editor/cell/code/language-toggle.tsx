/* Copyright 2024 Marimo. All rights reserved. */
import { switchLanguage } from "@/core/codemirror/language/extension";
import type { EditorView } from "@codemirror/view";
import type React from "react";
import { MarkdownIcon, PythonIcon } from "./icons";
import { Button } from "@/components/ui/button";
import { Tooltip } from "@/components/ui/tooltip";
import type { LanguageAdapter } from "@/core/codemirror/language/types";
import { DatabaseIcon } from "lucide-react";
import { useMemo } from "react";
import { MarkdownLanguageAdapter } from "@/core/codemirror/language/languages/markdown";
import { SQLLanguageAdapter } from "@/core/codemirror/language/languages/sql";
import { Functions } from "@/utils/functions";

interface LanguageTogglesProps {
  editorView: EditorView | null;
  code: string;
  currentLanguageAdapter: LanguageAdapter["type"] | undefined;
  onAfterToggle: () => void;
}

export const LanguageToggles: React.FC<LanguageTogglesProps> = ({
  editorView,
  code,
  currentLanguageAdapter,
  onAfterToggle,
}) => {
  const canUseMarkdown = useMemo(
    () => new MarkdownLanguageAdapter().isSupported(code) || code.trim() === "",
    [code],
  );
  const canUseSQL = useMemo(
    () => new SQLLanguageAdapter().isSupported(code) || code.trim() === "",
    [code],
  );

  return (
    <div className="absolute right-3 top-2 z-20 flex hover-action gap-1">
      <LanguageToggle
        editorView={editorView}
        currentLanguageAdapter={currentLanguageAdapter}
        canSwitchToLanguage={canUseSQL && currentLanguageAdapter === "python"}
        icon={
          <DatabaseIcon
            color={"var(--sky-11)"}
            strokeWidth={2.5}
            className="w-4 h-4"
          />
        }
        toType="sql"
        displayName="SQL"
        onAfterToggle={onAfterToggle}
      />
      <LanguageToggle
        editorView={editorView}
        currentLanguageAdapter={currentLanguageAdapter}
        canSwitchToLanguage={
          canUseMarkdown && currentLanguageAdapter === "python"
        }
        icon={
          <MarkdownIcon
            fill={"var(--sky-11)"}
            color="black"
            className="w-4 h-4"
          />
        }
        toType="markdown"
        displayName="Markdown"
        onAfterToggle={onAfterToggle}
      />
      <LanguageToggle
        editorView={editorView}
        currentLanguageAdapter={currentLanguageAdapter}
        canSwitchToLanguage={true}
        icon={
          <PythonIcon
            fill={"var(--sky-11)"}
            color="black"
            className="w-4 h-4"
          />
        }
        toType="python"
        displayName="Python"
        onAfterToggle={Functions.NOOP}
      />
    </div>
  );
};

interface Props {
  className?: string;
  editorView: EditorView | null;
  canSwitchToLanguage: boolean;
  currentLanguageAdapter: LanguageAdapter["type"] | undefined;
  toType: LanguageAdapter["type"];
  displayName: string;
  icon: React.ReactNode;
  onAfterToggle: () => void;
}

export const LanguageToggle: React.FC<Props> = ({
  editorView,
  currentLanguageAdapter,
  canSwitchToLanguage,
  icon,
  toType,
  displayName,
  onAfterToggle,
}) => {
  const handleClick = () => {
    if (!editorView) {
      return;
    }
    switchLanguage(editorView, toType);
    onAfterToggle();
  };

  if (!canSwitchToLanguage) {
    return null;
  }

  if (currentLanguageAdapter === toType) {
    return null;
  }

  return (
    <Tooltip content={`View as ${displayName}`}>
      <Button
        data-testid="language-toggle-button"
        variant="text"
        size="xs"
        className="opacity-80 px-1"
        onClick={handleClick}
      >
        {icon}
      </Button>
    </Tooltip>
  );
};
