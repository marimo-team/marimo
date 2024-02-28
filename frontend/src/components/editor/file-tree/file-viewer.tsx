/* Copyright 2024 Marimo. All rights reserved. */
import { sendFileDetails } from "@/core/network/requests";
import { FileInfo } from "@/core/network/types";
import { useAsyncData } from "@/hooks/useAsyncData";
import AnyLanguageCodeMirror from "@/plugins/impl/code/any-language-editor";
import { ErrorBanner } from "@/plugins/impl/common/error-banner";
import { EditorView } from "@codemirror/view";
import React from "react";

interface Props {
  file: FileInfo;
}

export const FileViewer: React.FC<Props> = ({ file }) => {
  const { data, loading, error } = useAsyncData(() => {
    return sendFileDetails({ path: file.path });
  }, [file.path]);

  if (error) {
    return <ErrorBanner error={error} />;
  }

  if (loading || !data) {
    return null;
  }

  if (!data.contents) {
    // Show details instead of contents
    return (
      <div className="grid grid-cols-2 gap-2 p-6">
        <div className="font-bold text-muted-foreground">Name</div>
        <div>{data.file.name}</div>
        <div className="font-bold text-muted-foreground">Type</div>
        <div>{data.mimeType}</div>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-auto">
      <AnyLanguageCodeMirror
        language={
          mimeToLanguage[data.mimeType || "default"] || mimeToLanguage.default
        }
        className="border-b"
        extensions={[EditorView.lineWrapping]}
        value={data.contents}
        readOnly={true}
      />
    </div>
  );
};

const mimeToLanguage: Record<string, string> = {
  "application/javascript": "javascript",
  "text/markdown": "markdown",
  "text/html": "html",
  "text/css": "css",
  "text/x-python": "python",
  "application/json": "json",
  "application/xml": "xml",
  "text/x-yaml": "yaml",
  default: "text",
};
