/* Copyright 2024 Marimo. All rights reserved. */

import { EditorView } from "@codemirror/view";
import { useAtomValue } from "jotai";
import { BetweenHorizontalStartIcon } from "lucide-react";
import { memo, Suspense, useState } from "react";
import { Streamdown, type StreamdownProps } from "streamdown";
import { Button, type ButtonProps } from "@/components/ui/button";
import { maybeAddMarimoImport } from "@/core/cells/add-missing-import";
import { useCellActions } from "@/core/cells/cells";
import { useLastFocusedCellId } from "@/core/cells/focus";
import { MarkdownLanguageAdapter } from "@/core/codemirror/language/languages/markdown";
import { SQLLanguageAdapter } from "@/core/codemirror/language/languages/sql/sql";
import { autoInstantiateAtom } from "@/core/config/config";
import { LazyAnyLanguageCodeMirror } from "@/plugins/impl/code/LazyAnyLanguageCodeMirror";
import { useTheme } from "@/theme/useTheme";
import { copyToClipboard } from "@/utils/copy";
import "./markdown-renderer.css";

const extensions = [EditorView.lineWrapping];

interface CodeBlockProps {
  code: string;
  language: string | undefined;
}

const SUPPORTED_LANGUAGES = new Set([
  "python",
  "markdown",
  "sql",
  "json",
  "yaml",
  "toml",
  "shell",
  "javascript",
  "typescript",
  "jsx",
  "tsx",
  "css",
  "html",
]);

function maybeTransform(
  language: string | undefined,
  code: string,
): {
  language: string;
  code: string;
} {
  // Default to python
  if (!language) {
    return { language: "python", code };
  }
  // Already in the right language
  if (language === "python") {
    return { language, code };
  }
  // Convert to python
  if (language === "sql") {
    return { language: "python", code: SQLLanguageAdapter.fromQuery(code) };
  }
  // Convert to python
  if (language === "markdown") {
    return {
      language: "python",
      code: MarkdownLanguageAdapter.fromMarkdown(code),
    };
  }
  // Run shell commands
  if (language === "shell" || language === "bash") {
    return {
      language: "python",
      code: `import subprocess\nsubprocess.run("${code}")`,
    };
  }
  // Store as a string
  return {
    language: "python",
    code: `_${language} = """\n${code}\n"""`,
  };
}

const InsertCodeBlockButton = ({ code, language }: CodeBlockProps) => {
  const { createNewCell } = useCellActions();
  const lastFocusedCellId = useLastFocusedCellId();
  const autoInstantiate = useAtomValue(autoInstantiateAtom);

  const handleInsertCode = () => {
    const result = maybeTransform(language, code);

    if (language === "sql") {
      maybeAddMarimoImport({
        autoInstantiate,
        createNewCell,
        fromCellId: lastFocusedCellId,
      });
    }
    createNewCell({
      code: result.code,
      before: false,
      cellId: lastFocusedCellId ?? "__end__",
    });
  };

  return (
    <Button size="xs" variant="outline" onClick={handleInsertCode}>
      Add to Notebook
      <BetweenHorizontalStartIcon className="ml-2 h-4 w-4" />
    </Button>
  );
};

const CodeBlock = ({ code, language }: CodeBlockProps) => {
  const { theme } = useTheme();
  const [value, setValue] = useState(code);

  if (value !== code) {
    setValue(code);
  }

  const handleCopyCode = async () => {
    await copyToClipboard(value);
  };

  return (
    <div className="relative">
      <Suspense>
        <LazyAnyLanguageCodeMirror
          theme={theme === "dark" ? "dark" : "light"}
          // Only show the language if it's supported
          language={
            language && SUPPORTED_LANGUAGES.has(language) ? language : undefined
          }
          className="cm border rounded overflow-hidden"
          extensions={extensions}
          value={value}
          onChange={setValue}
        />
      </Suspense>
      <div className="flex justify-end mt-2 space-x-2">
        <CopyButton size="xs" variant="outline" onClick={handleCopyCode}>
          Copy
        </CopyButton>
        <InsertCodeBlockButton code={value} language={language} />
      </div>
    </div>
  );
};

const CopyButton: React.FC<ButtonProps> = ({ onClick, ...props }) => {
  const [copied, setCopied] = useState(false);

  return (
    <Button
      {...props}
      onClick={(e) => {
        onClick?.(e);
        setCopied(true);
        setTimeout(() => setCopied(false), 1000);
      }}
    >
      {copied ? "Copied" : "Copy"}
    </Button>
  );
};

type Components = StreamdownProps["components"];

const COMPONENTS: Components = {
  code: ({ children, className }) => {
    const language = className?.replace("language-", "");
    if (language && typeof children === "string") {
      const code = children.trim();
      return (
        <div>
          <div className="text-xs text-muted-foreground pl-1">{language}</div>
          <CodeBlock code={code} language={language} />
        </div>
      );
    }
    return <code className={className}>{children}</code>;
  },
};

export const MarkdownRenderer = memo(({ content }: { content: string }) => {
  return (
    <Streamdown components={COMPONENTS} className="mo-markdown-renderer">
      {content}
    </Streamdown>
  );
});
MarkdownRenderer.displayName = "MarkdownRenderer";
