/* Copyright 2026 Marimo. All rights reserved. */

import { useAtomValue } from "jotai";
import { MarkdownRenderer } from "@/components/markdown/markdown-renderer";
import { aiAtom } from "@/core/config/config";

export function ChatMarkdown({ content }: { content: string }) {
  const mode = useAtomValue(aiAtom)?.mode;
  return (
    <MarkdownRenderer
      content={content}
      allowNotebookInsertion={mode !== "agent" && mode !== "code_mode"}
    />
  );
}
