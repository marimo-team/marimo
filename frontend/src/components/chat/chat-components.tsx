/* Copyright 2026 Marimo. All rights reserved. */

import type { FileUIPart } from "ai";
import {
  AtSignIcon,
  FileIcon,
  FileTextIcon,
  ImageIcon,
  PaperclipIcon,
  SendHorizontalIcon,
  SquareIcon,
  XIcon,
} from "lucide-react";
import { useState } from "react";
import { cn } from "@/utils/cn";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import { Tooltip } from "../ui/tooltip";
import { SUPPORTED_ATTACHMENT_TYPES } from "./chat-utils";

export const AttachmentRenderer = ({
  attachment,
}: {
  attachment: FileUIPart;
}) => {
  if (attachment.mediaType?.startsWith("image/")) {
    return (
      <img
        src={attachment.url}
        alt={attachment.filename || "Attachment"}
        className="max-h-[100px] max-w-[100px] object-contain mb-1.5"
      />
    );
  }

  return (
    <div className="flex flex-row gap-1 items-center text-xs">
      <FileIcon className="h-3 w-3 mt-0.5" />
      {attachment.filename || "Attachment"}
    </div>
  );
};

export const FileAttachmentPill = ({
  file,
  className,
  onRemove,
}: {
  file: File;
  className?: string;
  onRemove: () => void;
}) => {
  const [isHovered, setIsHovered] = useState(false);

  return (
    <div
      className={cn(
        "py-1 px-1.5 bg-muted rounded-md cursor-pointer flex flex-row gap-1 items-center text-xs",
        className,
      )}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      {isHovered ? (
        <XIcon className="h-3 w-3 mt-0.5" onClick={onRemove} />
      ) : (
        renderFileIcon(file)
      )}
      {file.name}
    </div>
  );
};

export const SendButton = ({
  isLoading,
  onStop,
  onSendClick,
  isEmpty,
}: {
  isLoading: boolean;
  onStop: () => void;
  onSendClick: () => void;
  isEmpty: boolean;
}) => {
  return (
    <Tooltip content={isLoading ? "Stop" : "Submit"}>
      <Button
        variant="text"
        size="sm"
        className="h-6 min-w-6 p-0 hover:bg-muted/30 cursor-pointer"
        onClick={isLoading ? onStop : onSendClick}
        disabled={isLoading ? false : isEmpty}
      >
        {isLoading ? (
          <SquareIcon className="h-3 w-3 fill-current text-error" />
        ) : (
          <SendHorizontalIcon className="h-3.5 w-3.5" />
        )}
      </Button>
    </Tooltip>
  );
};

export const AddContextButton = ({
  handleAddContext,
  isLoading,
}: {
  handleAddContext: () => void;
  isLoading: boolean;
}) => {
  return (
    <Tooltip content="Add context">
      <Button
        variant="text"
        size="icon"
        onClick={handleAddContext}
        disabled={isLoading}
      >
        <AtSignIcon className="h-3.5 w-3.5" />
      </Button>
    </Tooltip>
  );
};

export const AttachFileButton = ({
  fileInputRef,
  isLoading,
  onAddFiles,
}: {
  fileInputRef: React.RefObject<HTMLInputElement | null>;
  isLoading: boolean;
  onAddFiles: (files: File[]) => void;
}) => {
  return (
    <>
      <Tooltip content="Attach a file">
        <Button
          variant="text"
          size="icon"
          onClick={() => fileInputRef.current?.click()}
          disabled={isLoading}
        >
          <PaperclipIcon className="h-3.5 w-3.5" />
        </Button>
      </Tooltip>
      <Input
        ref={fileInputRef}
        type="file"
        multiple={true}
        hidden={true}
        onChange={(event: React.ChangeEvent<HTMLInputElement>) => {
          if (event.target.files) {
            onAddFiles([...event.target.files]);
          }
        }}
        accept={SUPPORTED_ATTACHMENT_TYPES.join(",")}
      />
    </>
  );
};

function renderFileIcon(file: File): React.ReactNode {
  const classNames = "h-3 w-3 mt-0.5";

  if (file.type.startsWith("image/")) {
    return <ImageIcon className={classNames} />;
  } else if (file.type.startsWith("text/")) {
    return <FileTextIcon className={classNames} />;
  }

  return <FileIcon className={classNames} />;
}
