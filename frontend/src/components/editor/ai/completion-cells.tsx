/* Copyright 2024 Marimo. All rights reserved. */

import { markdown } from "@codemirror/lang-markdown";
import { sql } from "@codemirror/lang-sql";
import ReactCodeMirror, { EditorView } from "@uiw/react-codemirror";
import { Button } from "@/components/ui/button";
import { customPythonLanguageSupport } from "@/core/codemirror/language/languages/python";
import type { ResolvedTheme } from "@/theme/useTheme";
import { cn } from "@/utils/cn";
import type { Language } from "./completion-utils";

export const baseExtensions = [
  customPythonLanguageSupport(),
  EditorView.lineWrapping,
];
const sqlExtensions = [sql(), EditorView.lineWrapping];
const markdownExtensions = [markdown(), EditorView.lineWrapping];

interface Props {
  code: string;
  onAccept: () => void;
  onDecline: () => void;
  theme: ResolvedTheme;
  language: Language;
  className?: string;
  displayActions?: boolean;
}

export const CompletionCellPreview: React.FC<Props> = ({
  code,
  onAccept,
  onDecline,
  theme,
  language,
  className,
  displayActions = true,
}) => {
  return (
    <div className={cn("flex flex-row relative", className)}>
      <div
        className="absolute top-0 left-0 h-full w-1 z-10 bg-green-600"
        data-testid="new-cell-gutter"
      />
      <ReactCodeMirror
        value={code}
        className="cm"
        theme={theme}
        extensions={
          language === "python"
            ? baseExtensions
            : language === "sql"
              ? sqlExtensions
              : markdownExtensions
        }
        editable={false}
        readOnly={true}
      />
      {displayActions && (
        <div className="flex flex-col justify-center p-2 gap-2">
          <Button
            size="xs"
            variant="text"
            className="h-6 w-6 text-green-600 hover:bg-green-600/10"
            onClick={onAccept}
            title="Accept this cell"
          >
            ✓
          </Button>
          <Button
            size="xs"
            variant="text"
            className="h-6 w-6 text-red-600 hover:bg-red-600/10"
            onClick={onDecline}
            title="Reject this cell"
          >
            ✕
          </Button>
        </div>
      )}
    </div>
  );
};
