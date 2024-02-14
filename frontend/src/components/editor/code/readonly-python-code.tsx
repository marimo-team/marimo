/* Copyright 2024 Marimo. All rights reserved. */
import { memo, useState } from "react";
import CodeMirror, {
  EditorView,
  ReactCodeMirrorProps,
} from "@uiw/react-codemirror";
import { CopyIcon, EyeIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Events } from "@/utils/events";
import { toast } from "@/components/ui/use-toast";
import { useTheme } from "@/theme/useTheme";
import { cn } from "@/utils/cn";
import { customPythonLanguageSupport } from "@/core/codemirror/language/python";

export const ReadonlyPythonCode = memo(
  (
    props: {
      className?: string;
      code: string;
      initiallyHideCode?: boolean;
    } & ReactCodeMirrorProps,
  ) => {
    const { theme } = useTheme();
    const { code, className, initiallyHideCode, ...rest } = props;
    const [hideCode, setHideCode] = useState(initiallyHideCode);

    return (
      <div className={cn("relative hover-actions-parent w-full", className)}>
        {hideCode && <HideCodeButton onClick={() => setHideCode(false)} />}
        {!hideCode && <FloatingCopyButton text={code} />}
        <CodeMirror
          {...rest}
          className={cn("cm", hideCode && "opacity-20 h-8 overflow-hidden")}
          theme={theme === "dark" ? "dark" : "light"}
          height="100%"
          editable={!hideCode}
          extensions={[customPythonLanguageSupport(), EditorView.lineWrapping]}
          value={code}
          readOnly={true}
        />
      </div>
    );
  },
);
ReadonlyPythonCode.displayName = "ReadonlyPythonCode";

const FloatingCopyButton = (props: { text: string }) => {
  const copy = Events.stopPropagation(() => {
    navigator.clipboard.writeText(props.text);
    toast({ title: "Copied to clipboard" });
  });

  return (
    <Button
      onClick={copy}
      className="absolute top-0 right-0 m-2 z-10 hover-action"
      size="xs"
      variant="secondary"
    >
      <CopyIcon size={14} strokeWidth={1.5} />
    </Button>
  );
};

export const HideCodeButton = (props: { onClick: () => void }) => {
  return (
    <div className="absolute inset-0 z-10" onClick={props.onClick}>
      <EyeIcon className="hover-action w-5 h-5 text-muted-foreground cursor-pointer absolute left-1/2 top-1/2 transform -translate-x-1/2 -translate-y-1/2 opacity-80 hover:opacity-100" />
    </div>
  );
};
