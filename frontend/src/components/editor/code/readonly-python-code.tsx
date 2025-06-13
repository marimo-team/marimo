/* Copyright 2024 Marimo. All rights reserved. */

import { sql } from "@codemirror/lang-sql";
import CodeMirror, {
  EditorView,
  type ReactCodeMirrorProps,
} from "@uiw/react-codemirror";
import { CopyIcon, EyeIcon, EyeOffIcon } from "lucide-react";
import { memo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Tooltip } from "@/components/ui/tooltip";
import { toast } from "@/components/ui/use-toast";
import { customPythonLanguageSupport } from "@/core/codemirror/language/languages/python";
import { useTheme } from "@/theme/useTheme";
import { cn } from "@/utils/cn";
import { copyToClipboard } from "@/utils/copy";
import { Events } from "@/utils/events";

const pythonExtensions = [
  customPythonLanguageSupport(),
  EditorView.lineWrapping,
];
const sqlExtensions = [sql(), EditorView.lineWrapping];

export const ReadonlyCode = memo(
  (
    props: {
      className?: string;
      code: string;
      initiallyHideCode?: boolean;
      language?: "python" | "sql";
    } & ReactCodeMirrorProps,
  ) => {
    const { theme } = useTheme();
    const {
      code,
      className,
      initiallyHideCode,
      language = "python",
      ...rest
    } = props;
    const [hideCode, setHideCode] = useState(initiallyHideCode);

    return (
      <div
        className={cn(
          "relative hover-actions-parent w-full overflow-hidden",
          className,
        )}
      >
        {hideCode && (
          <HideCodeButton
            tooltip="Show code"
            onClick={() => setHideCode(false)}
          />
        )}
        {!hideCode && (
          <div className="absolute top-0 right-0 my-1 mx-2 z-10 hover-action flex gap-2">
            <CopyButton text={code} />

            <EyeCloseButton onClick={() => setHideCode(true)} />
          </div>
        )}
        <CodeMirror
          {...rest}
          className={cn("cm", hideCode && "opacity-20 h-8 overflow-hidden")}
          theme={theme === "dark" ? "dark" : "light"}
          height="100%"
          editable={!hideCode}
          extensions={language === "python" ? pythonExtensions : sqlExtensions}
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

const EyeCloseButton = (props: { onClick: () => void }) => {
  return (
    <Tooltip content="Hide code" usePortal={false}>
      <Button
        onClick={props.onClick}
        size="xs"
        className="py-0"
        variant="secondary"
      >
        <EyeOffIcon size={14} strokeWidth={1.5} />
      </Button>
    </Tooltip>
  );
};

export const HideCodeButton = (props: {
  tooltip?: string;
  className?: string;
  onClick: () => void;
}) => {
  return (
    <div className={props.className} onClick={props.onClick}>
      <Tooltip usePortal={false} content={props.tooltip}>
        <EyeIcon className="hover-action w-5 h-5 text-muted-foreground cursor-pointer absolute left-1/2 top-1/2 transform -translate-x-1/2 -translate-y-1/2 opacity-80 hover:opacity-100 z-20" />
      </Tooltip>
    </div>
  );
};
