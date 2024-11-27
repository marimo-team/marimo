/* Copyright 2024 Marimo. All rights reserved. */
import { useTheme } from "@/theme/useTheme";
import { LazyAnyLanguageCodeMirror } from "@/plugins/impl/code/LazyAnyLanguageCodeMirror";
import { useCellActions } from "@/core/cells/cells";
import { Button } from "@/components/ui/button";
import { BetweenHorizontalStartIcon } from "lucide-react";
import { EditorView } from "@codemirror/view";
import Markdown, { type Components } from "react-markdown";
import { useEffect, useState } from "react";
import { useLastFocusedCellId } from "@/core/cells/focus";
import { copyToClipboard } from "@/utils/copy";
import { SQLLanguageAdapter } from "@/core/codemirror/language/sql";
import { maybeAddMarimoImport } from "@/core/cells/add-missing-import";
import { useAtomValue } from "jotai";
import { autoInstantiateAtom } from "@/core/config/config";
import { MarkdownLanguageAdapter } from "@/core/codemirror/language/markdown";

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

const CodeBlock = ({ code, language }: CodeBlockProps) => {
  const { theme } = useTheme();
  const { createNewCell } = useCellActions();
  const lastFocusedCellId = useLastFocusedCellId();
  const autoInstantiate = useAtomValue(autoInstantiateAtom);
  const [value, setValue] = useState(code);

  useEffect(() => {
    setValue(code);
  }, [code]);

  const handleInsertCode = () => {
    const result = maybeTransform(language, value);

    if (language === "sql") {
      maybeAddMarimoImport(autoInstantiate, createNewCell, lastFocusedCellId);
    }
    createNewCell({
      code: result.code,
      before: false,
      cellId: lastFocusedCellId ?? "__end__",
    });
  };

  const handleCopyCode = async () => {
    await copyToClipboard(value);
  };

  return (
    <div className="relative">
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
      <div className="flex justify-end mt-2 space-x-2">
        <Button size="xs" variant="outline" onClick={handleCopyCode}>
          Copy
        </Button>
        <Button size="xs" variant="outline" onClick={handleInsertCode}>
          Add to Notebook
          <BetweenHorizontalStartIcon className="ml-2 h-4 w-4" />
        </Button>
      </div>
    </div>
  );
};

const COMPONENTS: Components = {
  code: ({ children, className }) => {
    const language = className?.replace("language-", "");
    if (language && typeof children === "string") {
      return (
        <div>
          <div className="text-xs text-muted-foreground pl-1">{language}</div>
          <CodeBlock code={children.trim()} language={language} />
        </div>
      );
    }
    return <code className={className}>{children}</code>;
  },
};

export const MarkdownRenderer = ({ content }: { content: string }) => {
  return (
    <Markdown
      components={COMPONENTS}
      className="prose dark:prose-invert max-w-none prose-pre:pl-0"
    >
      {content}
    </Markdown>
  );
};
