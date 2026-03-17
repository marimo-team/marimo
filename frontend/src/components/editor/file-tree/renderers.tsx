/* Copyright 2026 Marimo. All rights reserved. */

import type { Extension } from "@codemirror/state";
import { EditorView } from "@codemirror/view";
import type { PaginationState } from "@tanstack/react-table";
import type React from "react";
import { Suspense, useMemo, useState } from "react";
import {
  generateColumns,
  inferFieldTypes,
} from "@/components/data-table/columns";
import { DataTable } from "@/components/data-table/data-table";
import { LazyAnyLanguageCodeMirror } from "@/plugins/impl/code/LazyAnyLanguageCodeMirror";
import { parseCsvData } from "@/plugins/impl/vega/loader";
import { useTheme } from "@/theme/useTheme";
import { Arrays } from "@/utils/arrays";
import { type Base64String, base64ToDataURL } from "@/utils/json/base64";
import { Objects } from "@/utils/objects";

const PAGE_SIZE = 25;

export function isMediaMime(mime: string): boolean {
  if (!mime) {
    return false;
  }
  return (
    mime.startsWith("image/") ||
    mime.startsWith("audio/") ||
    mime.startsWith("video/") ||
    mime.startsWith("application/pdf")
  );
}

export const MIME_TO_LANGUAGE: Record<string, string> = {
  "application/javascript": "javascript",
  "text/markdown": "markdown",
  "text/html": "html",
  "text/css": "css",
  "text/x-python": "python",
  "application/json": "json",
  "application/xml": "xml",
  "text/x-yaml": "yaml",
  "text/csv": "markdown",
  "text/plain": "markdown",
  default: "markdown",
};

/**
 * Media viewer props: provide either a direct `url` or `base64` + `mime`.
 * When `url` is set it takes precedence.
 */
export type MediaSource =
  | { url: string; base64?: undefined; mime?: string }
  | { url?: undefined; base64: Base64String; mime: string };

function resolveMediaSrc(source: MediaSource): string {
  if (source.url != null) {
    return source.url;
  }
  return base64ToDataURL(source.base64, source.mime);
}

export const CsvViewer: React.FC<{ contents: string }> = ({ contents }) => {
  const data = useMemo(() => parseCsvData(contents), [contents]);
  const [pagination, setPagination] = useState<PaginationState>({
    pageIndex: 0,
    pageSize: PAGE_SIZE,
  });
  const fieldTypes = useMemo(() => inferFieldTypes(data), [data]);
  const columns = useMemo(
    () =>
      generateColumns<object>({
        rowHeaders: Arrays.EMPTY,
        selection: null,
        fieldTypes,
      }),
    [fieldTypes],
  );

  return (
    <DataTable<object>
      data={data}
      totalRows={data.length}
      columns={columns}
      totalColumns={columns.length}
      manualPagination={false}
      paginationState={pagination}
      setPaginationState={setPagination}
      wrapperClassName="h-full justify-between pb-1 px-1"
      pagination={true}
      className="rounded-none border-b flex overflow-hidden"
      rowSelection={Objects.EMPTY}
    />
  );
};

export const ImageViewer: React.FC<MediaSource> = (props) => {
  return <img src={resolveMediaSrc(props)} alt="Preview" />;
};

export const AudioViewer: React.FC<MediaSource> = (props) => {
  return <audio controls={true} src={resolveMediaSrc(props)} />;
};

export const VideoViewer: React.FC<MediaSource> = (props) => {
  return <video controls={true} src={resolveMediaSrc(props)} />;
};

export const PdfViewer: React.FC<MediaSource> = (props) => {
  return (
    <iframe
      src={resolveMediaSrc(props)}
      title="PDF Viewer"
      className="w-full h-full"
    />
  );
};

/**
 * Renders the appropriate media viewer for the given mime type.
 * Accepts either a `url` or `base64` + `mime` via {@link MediaSource}.
 */
export const MediaRenderer: React.FC<MediaSource & { mimeType: string }> = ({
  mimeType,
  ...source
}) => {
  if (mimeType.startsWith("image/")) {
    return <ImageViewer {...source} />;
  }
  if (mimeType.startsWith("audio/")) {
    return <AudioViewer {...source} />;
  }
  if (mimeType.startsWith("video/")) {
    return <VideoViewer {...source} />;
  }
  if (mimeType.startsWith("application/pdf")) {
    return <PdfViewer {...source} />;
  }
  return null;
};

/**
 * Unified content renderer that dispatches to the appropriate viewer
 * based on MIME type. Used by both the local file viewer and the
 * storage file viewer.
 */
export const FileContentRenderer: React.FC<{
  mimeType: string;
  /** Text content for text/CSV files. */
  contents?: string;
  /** Media source for image/audio/video/PDF files. */
  mediaSource?: MediaSource;
  readOnly?: boolean;
  onChange?: (value: string) => void;
  /** Additional CodeMirror extensions (e.g. save hotkey). */
  extensions?: Extension[];
}> = ({
  mimeType,
  contents,
  mediaSource,
  readOnly = true,
  onChange,
  extensions = [],
}) => {
  const { theme } = useTheme();

  if (mimeType === "text/csv" && contents != null) {
    return (
      <div className="flex-1 overflow-hidden flex flex-col">
        <CsvViewer contents={contents} />
      </div>
    );
  }

  if (isMediaMime(mimeType) && mediaSource) {
    return (
      <div className="flex-1 overflow-hidden flex flex-col">
        <MediaRenderer {...mediaSource} mimeType={mimeType} />
      </div>
    );
  }

  if (contents != null) {
    const language = MIME_TO_LANGUAGE[mimeType] || MIME_TO_LANGUAGE.default;
    return (
      <div className="flex-1 overflow-auto">
        <Suspense>
          <LazyAnyLanguageCodeMirror
            theme={theme === "dark" ? "dark" : "light"}
            language={language}
            className="border-b"
            extensions={[EditorView.lineWrapping, ...extensions]}
            value={contents}
            readOnly={readOnly}
            editable={readOnly ? false : undefined}
            onChange={readOnly ? undefined : onChange}
          />
        </Suspense>
      </div>
    );
  }

  return null;
};
