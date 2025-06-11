/* Copyright 2024 Marimo. All rights reserved. */
import { sendFileDetails, sendUpdateFile } from "@/core/network/requests";
import type { FileInfo } from "@/core/network/types";
import { useAsyncData } from "@/hooks/useAsyncData";
import { LazyAnyLanguageCodeMirror } from "@/plugins/impl/code/LazyAnyLanguageCodeMirror";
import { ErrorBanner } from "@/plugins/impl/common/error-banner";
import { useTheme } from "@/theme/useTheme";
import { EditorView, keymap } from "@codemirror/view";
import type React from "react";
import { useEffect, useRef, useState } from "react";
import { Button } from "../inputs/Inputs";
import {
  CopyIcon,
  DownloadIcon,
  ExternalLinkIcon,
  SaveIcon,
} from "lucide-react";
import { renderShortcut } from "@/components/shortcuts/renderShortcut";
import { Tooltip } from "@/components/ui/tooltip";
import { downloadBlob, downloadByURL } from "@/utils/download";
import { type Base64String, base64ToDataURL } from "@/utils/json/base64";
import { hotkeysAtom } from "@/core/config/config";
import { useAtomValue } from "jotai";
import { ImageViewer, CsvViewer, AudioViewer, VideoViewer } from "./renderers";
import { isWasm } from "@/core/wasm/utils";
import { copyToClipboard } from "@/utils/copy";

interface Props {
  file: FileInfo;
  onOpenNotebook: (
    evt: Pick<Event, "stopPropagation" | "preventDefault">,
  ) => void;
}

const unsavedContentsForFile = new Map<string, string>();

export const FileViewer: React.FC<Props> = ({ file, onOpenNotebook }) => {
  const { theme } = useTheme();
  const hotkeys = useAtomValue(hotkeysAtom);
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
          setData((prev) => ({ ...prev, contents: internalValue }));
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
      if (!data?.contents) {
        return;
      }
      const draft = internalValueRef.current;
      if (draft === data.contents) {
        unsavedContentsForFile.delete(file.path);
      } else {
        unsavedContentsForFile.set(file.path, draft);
      }
    };
  }, [file.path, data?.contents]);

  if (error) {
    return <ErrorBanner error={error} />;
  }

  if (loading || !data) {
    return null;
  }

  const mimeType = data.mimeType || "text/plain";
  const isEditable = mimeType in mimeToLanguage;

  if (!data.contents && !isEditable) {
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
      {file.isMarimoFile && !isWasm() && (
        <Tooltip content="Open notebook">
          <Button size="small" onClick={(evt) => onOpenNotebook(evt)}>
            <ExternalLinkIcon />
          </Button>
        </Tooltip>
      )}
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
              onClick={async () => {
                await copyToClipboard(internalValue);
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

  if (mimeType === "text/csv" && data.contents) {
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
                key: hotkeys.getHotkey("global.save").key,
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
