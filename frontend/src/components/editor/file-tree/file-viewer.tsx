/* Copyright 2026 Marimo. All rights reserved. */

import { keymap } from "@codemirror/view";
import { useAtomValue } from "jotai";
import {
  AlertTriangleIcon,
  CopyIcon,
  ExternalLinkIcon,
  SaveIcon,
} from "lucide-react";
import type React from "react";
import { useEffect, useRef, useState } from "react";
import { renderShortcut } from "@/components/shortcuts/renderShortcut";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Tooltip } from "@/components/ui/tooltip";
import { disableFileDownloadsAtom, hotkeysAtom } from "@/core/config/config";
import { useRequestClient } from "@/core/network/requests";
import type { FileInfo } from "@/core/network/types";
import { filenameAtom } from "@/core/saving/file-state";
import { isWasm } from "@/core/wasm/utils";
import { useAsyncData } from "@/hooks/useAsyncData";
import { ErrorBanner } from "@/plugins/impl/common/error-banner";
import { copyToClipboard } from "@/utils/copy";
import { downloadBlob, downloadByURL } from "@/utils/download";
import { type Base64String, base64ToDataURL } from "@/utils/json/base64";
import { FilePreviewHeader } from "./file-header";
import {
  FileContentRenderer,
  isMediaMime,
  MIME_TO_LANGUAGE,
} from "./renderers";

interface Props {
  file: FileInfo;
  onOpenNotebook: (
    evt: Pick<Event, "stopPropagation" | "preventDefault">,
  ) => void;
}

const unsavedContentsForFile = new Map<string, string>();

export const FileViewer: React.FC<Props> = ({ file, onOpenNotebook }) => {
  const { sendFileDetails, sendUpdateFile } = useRequestClient();
  const hotkeys = useAtomValue(hotkeysAtom);
  const disableFileDownloads = useAtomValue(disableFileDownloadsAtom);
  const currentNotebookFilename = useAtomValue(filenameAtom);
  // undefined value means not modified yet
  const [internalValue, setInternalValue] = useState<string>("");

  const { data, isPending, error, setData, refetch } =
    useAsyncData(async () => {
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

  if (isPending || !data) {
    return null;
  }

  const mimeType = data.mimeType || "text/plain";
  const isEditable = mimeType in MIME_TO_LANGUAGE;
  const isActiveNotebook =
    currentNotebookFilename &&
    data.file.isMarimoFile &&
    (file.path === currentNotebookFilename ||
      // This may capture other notebook files in subdirectories
      // but this is an okay heuristic for now.
      file.path.endsWith(`/${currentNotebookFilename}`));

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
    if (isMediaMime(mimeType)) {
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
    <FilePreviewHeader
      filename={data.file.name}
      onRefresh={refetch}
      onDownload={disableFileDownloads ? undefined : handleDownload}
      actions={
        <>
          {file.isMarimoFile && !isWasm() && (
            <Tooltip content="Open notebook">
              <Button
                variant="text"
                size="xs"
                onClick={(evt) => onOpenNotebook(evt)}
              >
                <ExternalLinkIcon className="h-3.5 w-3.5" />
              </Button>
            </Tooltip>
          )}
          {!isMediaMime(mimeType) && (
            <>
              <Tooltip content="Copy contents to clipboard">
                <Button
                  variant="text"
                  size="xs"
                  onClick={async () => {
                    await copyToClipboard(internalValue);
                  }}
                >
                  <CopyIcon className="h-3.5 w-3.5" />
                </Button>
              </Tooltip>
              <Tooltip content={renderShortcut("global.save")}>
                <Button
                  variant={internalValue === data.contents ? "text" : "success"}
                  size="xs"
                  onClick={handleSaveFile}
                  disabled={internalValue === data.contents}
                >
                  <SaveIcon className="h-3.5 w-3.5" />
                </Button>
              </Tooltip>
            </>
          )}
        </>
      }
    />
  );

  const isMedia = isMediaMime(mimeType);
  const isText = !isMedia && mimeType !== "text/csv";

  const warningBanner = isText && isActiveNotebook && (
    <Alert variant="warning" className="rounded-none">
      <AlertTriangleIcon className="h-4 w-4" />
      <AlertDescription>
        Editing the notebook file directly while running in marimo's editor may
        cause unintended changes. Please use with caution.
      </AlertDescription>
    </Alert>
  );

  return (
    <>
      {header}
      {warningBanner}
      <FileContentRenderer
        mimeType={mimeType}
        contents={
          isMedia
            ? undefined
            : isText
              ? internalValue
              : (data.contents ?? undefined)
        }
        mediaSource={
          isMedia
            ? { base64: data.contents as Base64String, mime: mimeType }
            : undefined
        }
        readOnly={!isText}
        onChange={setInternalValue}
        extensions={[
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
      />
    </>
  );
};
