/* Copyright 2026 Marimo. All rights reserved. */

import { markdown } from "@codemirror/lang-markdown";
import { sql } from "@codemirror/lang-sql";
import {
  defaultHighlightStyle,
  syntaxHighlighting,
} from "@codemirror/language";
import CodeMirror, {
  EditorView,
  type ReactCodeMirrorProps,
} from "@uiw/react-codemirror";
import { CopyIcon, EyeIcon, EyeOffIcon, PlusIcon } from "lucide-react";
import { memo, useMemo, useState } from "react";
import { useAddCodeToNewCell } from "@/components/editor/cell/useAddCell";
import { Button } from "@/components/ui/button";
import { Tooltip } from "@/components/ui/tooltip";
import { toast } from "@/components/ui/use-toast";
import type { LanguageAdapterType } from "@/core/codemirror/language/types";
import { customPythonLanguageSupport } from "@/core/codemirror/language/languages/python";
import { darkTheme } from "@/core/codemirror/theme/dark";
import { lightTheme } from "@/core/codemirror/theme/light";
import { useTheme } from "@/theme/useTheme";
import { cn } from "@/utils/cn";
import { copyToClipboard } from "@/utils/copy";
import { Events } from "@/utils/events";

const pythonExtensions = [
  customPythonLanguageSupport(),
  EditorView.lineWrapping,
];
const sqlExtensions = [sql(), EditorView.lineWrapping];
const markdownExtensions = [markdown(), EditorView.lineWrapping];

function readonlyCodeExtensions(language: LanguageAdapterType) {
  switch (language) {
    case "sql":
      return sqlExtensions;
    case "markdown":
      return markdownExtensions;
    default:
      return pythonExtensions;
  }
}

/**
 * A readonly code component that can be used to display code in a readonly state.
 *
 * @param props.className - The class name to apply to the component.
 * @param props.code - The code to display.
 * @param props.initiallyHideCode - Whether to initially hide the code.
 * @param props.showHideCode - Whether to show the hide code button.
 * @param props.insertNewCell - Whether to add a insert new cell button; when clicked will add a new cell next to the current cell or at the end of the file
 * @param props.language - The language of the code. Default is "python".
 */
export const ReadonlyCode = memo(
  (
    props: {
      className?: string;
      code: string;
      initiallyHideCode?: boolean;
      showHideCode?: boolean;
      showCopyCode?: boolean;
      insertNewCell?: boolean;
      language?: LanguageAdapterType;
    } & ReactCodeMirrorProps,
  ) => {
    const { theme } = useTheme();
    const {
      code,
      className,
      initiallyHideCode,
      showHideCode = true,
      showCopyCode = true,
      insertNewCell,
      language = "python",
      ...rest
    } = props;
    const [hideCode, setHideCode] = useState(initiallyHideCode);

    const extensions = useMemo(
      () => [
        theme === "dark" ? darkTheme : lightTheme,
        syntaxHighlighting(defaultHighlightStyle, { fallback: true }),
        ...readonlyCodeExtensions(language),
      ],
      [theme, language],
    );

    return (
      <div
        className={cn(
          "relative hover-actions-parent w-full overflow-hidden pb-1",
          className,
        )}
      >
        <div className="absolute top-0 right-0 my-1 mx-2 z-10 hover-action flex gap-2">
          {showCopyCode && <CopyButton text={code} />}
          {insertNewCell && <InsertNewCell code={code} />}
          {showHideCode && (
            <ToggleCodeButton
              hidden={hideCode ?? false}
              onClick={() => setHideCode(!hideCode)}
            />
          )}
        </div>
        <CodeMirror
          {...rest}
          className={cn("cm", hideCode && "opacity-20 h-8 overflow-hidden")}
          theme="none"
          height="100%"
          editable={false}
          extensions={extensions}
          value={code}
          readOnly={true}
        />
      </div>
    );
  },
);
ReadonlyCode.displayName = "ReadonlyCode";

const CopyButton = (props: { text: string }) => {
  const copy = Events.stopPropagation(async () => {
    await copyToClipboard(props.text);
    toast({ title: "Copied to clipboard" });
  });

  return (
    <Tooltip content="Copy code" usePortal={false}>
      <Button onClick={copy} size="xs" className="py-0" variant="secondary">
        <CopyIcon size={14} strokeWidth={1.5} />
      </Button>
    </Tooltip>
  );
};

const ToggleCodeButton = (props: { hidden: boolean; onClick: () => void }) => {
  return (
    <Tooltip
      content={props.hidden ? "Show code" : "Hide code"}
      usePortal={false}
    >
      <Button
        onClick={props.onClick}
        size="xs"
        className="py-0"
        variant="secondary"
      >
        {props.hidden ? (
          <EyeIcon size={14} strokeWidth={1.5} />
        ) : (
          <EyeOffIcon size={14} strokeWidth={1.5} />
        )}
      </Button>
    </Tooltip>
  );
};

const InsertNewCell = (props: { code: string }) => {
  const addCodeToNewCell = useAddCodeToNewCell();

  const handleClick = () => {
    addCodeToNewCell(props.code);
  };

  return (
    <Tooltip content="Add code to notebook" usePortal={false}>
      <Button
        onClick={handleClick}
        size="xs"
        className="py-0"
        variant="secondary"
      >
        <PlusIcon size={14} strokeWidth={1.5} />
      </Button>
    </Tooltip>
  );
};
