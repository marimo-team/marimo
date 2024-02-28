/* Copyright 2024 Marimo. All rights reserved. */
import { generateColumns } from "@/components/data-table/columns";
import { DataTable } from "@/components/data-table/data-table";
import { sendFileDetails } from "@/core/network/requests";
import { FileInfo } from "@/core/network/types";
import { useAsyncData } from "@/hooks/useAsyncData";
import AnyLanguageCodeMirror from "@/plugins/impl/code/any-language-editor";
import { ErrorBanner } from "@/plugins/impl/common/error-banner";
import { parseCsvData } from "@/plugins/impl/vega/loader";
import { Objects } from "@/utils/objects";
import { EditorView } from "@codemirror/view";
import React, { useMemo } from "react";

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

  if (data.mimeType === "text/csv") {
    return (
      <div className="flex-1 overflow-hidden flex flex-col">
        <CsvViewer contents={data.contents} />
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

const CsvViewer: React.FC<{ contents: string }> = ({ contents }) => {
  const data = useMemo(() => parseCsvData(contents), [contents]);
  const columns = useMemo(() => generateColumns(data, [], null), [data]);

  return (
    <DataTable
      data={data}
      columns={columns}
      wrapperClassName="h-full justify-between pb-1 px-1"
      pagination={true}
      pageSize={10}
      className="rounded-none border-b flex overflow-hidden"
      rowSelection={Objects.EMPTY}
    />
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
  "text/csv": "markdown",
  default: "markdown",
};
