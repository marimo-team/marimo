/* Copyright 2023 Marimo. All rights reserved. */
import React from "react";
import CodeMirror, { minimalSetup } from "@uiw/react-codemirror";
import { python } from "@codemirror/lang-python";

import "./TinyCode.css";
import { useTheme } from "@/theme/useTheme";

interface Props {
  code: string;
}

export const TinyCode: React.FC<Props> = ({ code }) => {
  const { theme } = useTheme();

  return (
    <div className="text-muted-foreground flex flex-col overflow-hidden">
      <CodeMirror
        minHeight="10px"
        theme={theme === "dark" ? "dark" : "light"}
        height="100%"
        className="tiny-code"
        editable={false}
        basicSetup={false}
        extensions={[
          python(),
          minimalSetup({
            syntaxHighlighting: true,
            // Rest false
            highlightSpecialChars: false,
            history: false,
            drawSelection: false,
            defaultKeymap: false,
            historyKeymap: false,
          }),
        ]}
        value={code}
      />
    </div>
  );
};
