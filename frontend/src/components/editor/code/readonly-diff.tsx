/* Copyright 2024 Marimo. All rights reserved. */
import { unifiedMergeView } from "@codemirror/merge";
import { EditorView } from "@codemirror/view";
import CodeMirror from "@uiw/react-codemirror";
import { memo, useMemo } from "react";
import { useTheme } from "@/theme/useTheme";

export const ReadonlyDiff = memo(
  (props: { original: string; modified: string }) => {
    const { theme } = useTheme();

    const extensions = useMemo(() => {
      return [
        EditorView.lineWrapping,
        unifiedMergeView({
          original: props.original,
          mergeControls: false,
          collapseUnchanged: {
            margin: 3,
            minSize: 4,
          },
        }),
      ];
    }, [props.original, props.modified, theme]);

    return (
      <CodeMirror
        className="cm font-mono"
        style={
          {
            "--marimo-code-editor-font-size": "10px",
          } as React.CSSProperties
        }
        extensions={extensions}
        readOnly={true}
        basicSetup={{
          lineNumbers: false,
          foldGutter: false,
          dropCursor: false,
          highlightActiveLineGutter: false,
          allowMultipleSelections: false,
          indentOnInput: false,
          bracketMatching: false,
          closeBrackets: false,
          autocompletion: false,
        }}
        theme={theme === "dark" ? "dark" : "light"}
        value={props.modified}
      />
    );
  },
);
ReadonlyDiff.displayName = "ReadonlyDiff";
