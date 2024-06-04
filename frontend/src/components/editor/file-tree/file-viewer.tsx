/* Copyright 2024 Marimo. All rights reserved. */
import { generateColumns } from "@/components/data-table/columns";
import { DataTable } from "@/components/data-table/data-table";
import { sendFileDetails, sendUpdateFile } from "@/core/network/requests";
import { FileInfo } from "@/core/network/types";
import { useAsyncData } from "@/hooks/useAsyncData";
import { LazyAnyLanguageCodeMirror } from "@/plugins/impl/code/LazyAnyLanguageCodeMirror";
import { ErrorBanner } from "@/plugins/impl/common/error-banner";
import { parseCsvData } from "@/plugins/impl/vega/loader";
import { useTheme } from "@/theme/useTheme";
import { Objects } from "@/utils/objects";
import { EditorView, keymap } from "@codemirror/view";
import React, { useEffect, useMemo, useRef, useState } from "react";
import { Button } from "../inputs/Inputs";
import { CopyIcon, DownloadIcon, SaveIcon } from "lucide-react";
import { renderShortcut } from "@/components/shortcuts/renderShortcut";
import { Tooltip } from "@/components/ui/tooltip";
import { HOTKEYS } from "@/core/hotkeys/hotkeys";
import { downloadBlob, downloadByURL } from "@/utils/download";
import { Base64String, base64ToDataURL } from "@/utils/json/base64";

interface Props {
  file: FileInfo;
}

const unsavedContentsForFile = new Map<string, string>();

export const FileViewer: React.FC<Props> = ({ file }) => {
  const { theme } = useTheme();
  // undefined value means not modified yet
  const [internalValue, setInternalValue] = useState<string>("");

  const { data, loading, error, setData } = useAsyncData(async () => {
    const details = await sendFileDetails({ path: file.path });
    const contents = details.contents || "";
    setInternalValue(unsavedContentsForFile.get(file.path) || contents);
    return details;
  }, [file.path]);

  const handleSaveFile = async () => {
    if (internalValue === data?.contents) {
      return;
    }

    await sendUpdateFile({ path: file.path, contents: internalValue }).then(
      (response) => {
        if (response.success) {
          // Update the last saved value
          setData((prev) =>
            prev ? { ...prev, contents: internalValue } : undefined,
          );
          setInternalValue(internalValue);
        }
      },
    );
  };

  // On file change or unmount, save the unsaved contents
  // We use a ref for internalValue so we don't call this effect on each keystroke
  const internalValueRef = useRef<string>(internalValue);
  internalValueRef.current = internalValue;
  useEffect(() => {
    return () => {
      if (!data) {
        return;
      }
      const draft = internalValueRef.current;
      if (draft === data.contents) {
        unsavedContentsForFile.delete(file.path);
      } else {
        unsavedContentsForFile.set(file.path, draft);
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [file.path, data?.contents]);

  if (error) {
    return <ErrorBanner error={error} />;
  }

  if (loading || !data) {
    return null;
  }

  const mimeType = data.mimeType || "text/plain";

  if (!data.contents) {
    // Show details instead of contents
    return (
      <div className="grid grid-cols-2 gap-2 p-6">
        <div className="font-bold text-muted-foreground">Name</div>
        <div>{data.file.name}</div>
        <div className="font-bold text-muted-foreground">Type</div>
        <div>{mimeType}</div>
      </div>
    );
  }

  const handleDownload = () => {
    if (isMedia(mimeType)) {
      const dataURL = base64ToDataURL(data.contents as Base64String, mimeType);
      downloadByURL(dataURL, data.file.name);
      return;
    }

    downloadBlob(
      new Blob([data.contents || internalValue], { type: mimeType }),
      data.file.name,
    );
  };

  const header = (
    <div className="text-xs text-muted-foreground p-1 flex justify-end gap-2 border-b">
      <Tooltip content="Download">
        <Button size="small" onClick={handleDownload}>
          <DownloadIcon />
        </Button>
      </Tooltip>
      {!isMedia(mimeType) && (
        <>
          <Tooltip content="Copy contents to clipboard">
            <Button
              size="small"
              onClick={() => {
                navigator.clipboard.writeText(internalValue);
              }}
            >
              <CopyIcon />
            </Button>
          </Tooltip>
          <Tooltip content={renderShortcut("global.save")}>
            <Button
              size="small"
              color={internalValue === data.contents ? undefined : "green"}
              onClick={handleSaveFile}
              disabled={internalValue === data.contents}
            >
              <SaveIcon />
            </Button>
          </Tooltip>
        </>
      )}
    </div>
  );

  if (mimeType.startsWith("image/")) {
    return (
      <>
        {header}
        <div className="flex-1 overflow-hidden flex flex-col">
          <ImageViewer base64={data.contents as Base64String} mime={mimeType} />
        </div>
      </>
    );
  }

  if (mimeType === "text/csv") {
    return (
      <>
        {header}
        <div className="flex-1 overflow-hidden flex flex-col">
          <CsvViewer contents={data.contents} />
        </div>
      </>
    );
  }

  if (mimeType.startsWith("audio/")) {
    return (
      <>
        {header}
        <div className="flex-1 overflow-hidden flex flex-col">
          <AudioViewer base64={data.contents as Base64String} mime={mimeType} />
        </div>
      </>
    );
  }

  if (mimeType.startsWith("video/")) {
    return (
      <>
        {header}
        <div className="flex-1 overflow-hidden flex flex-col">
          <VideoViewer base64={data.contents as Base64String} mime={mimeType} />
        </div>
      </>
    );
  }

  return (
    <>
      {header}
      <div className="flex-1 overflow-auto">
        <LazyAnyLanguageCodeMirror
          theme={theme === "dark" ? "dark" : "light"}
          language={mimeToLanguage[mimeType] || mimeToLanguage.default}
          className="border-b"
          extensions={[
            EditorView.lineWrapping,
            // Command S for save
            keymap.of([
              {
                key: HOTKEYS.getHotkey("global.save").key,
                stopPropagation: true,
                run: () => {
                  if (internalValue !== data.contents) {
                    handleSaveFile();
                    return true;
                  }
                  return false;
                },
              },
            ]),
          ]}
          value={internalValue}
          onChange={setInternalValue}
        />
      </div>
    </>
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

const ImageViewer: React.FC<{ base64: Base64String; mime: string }> = ({
  mime,
  base64,
}) => {
  return <img src={base64ToDataURL(base64, mime)} alt="Preview" />;
};

const AudioViewer: React.FC<{ base64: Base64String; mime: string }> = ({
  mime,
  base64,
}) => {
  // eslint-disable-next-line jsx-a11y/media-has-caption
  return <audio controls={true} src={base64ToDataURL(base64, mime)} />;
};

const VideoViewer: React.FC<{ base64: Base64String; mime: string }> = ({
  mime,
  base64,
}) => {
  // eslint-disable-next-line jsx-a11y/media-has-caption
  return <video controls={true} src={base64ToDataURL(base64, mime)} />;
};

const isMedia = (mime: string) => {
  if (!mime) {
    return false;
  }
  return (
    mime.startsWith("image/") ||
    mime.startsWith("audio/") ||
    mime.startsWith("video/")
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
  "text/plain": "markdown",
  default: "markdown",
};
