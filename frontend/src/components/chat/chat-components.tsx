/* Copyright 2024 Marimo. All rights reserved. */

import { FileIcon, FileTextIcon, ImageIcon, XIcon } from "lucide-react";
import { useState } from "react";
import type { ChatAttachment } from "@/core/ai/types";
import { cn } from "@/utils/cn";

export const AttachmentRenderer = ({
  attachment,
}: {
  attachment: ChatAttachment;
}) => {
  if (attachment.contentType?.startsWith("image/")) {
    return (
      <img
        src={attachment.url}
        alt={attachment.name}
        className="max-h-[100px] max-w-[100px] object-contain mb-1.5"
      />
    );
  }

  return (
    <div className="flex flex-row gap-1 items-center text-xs">
      <FileIcon className="h-3 w-3 mt-0.5" />
      {attachment.name}
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

function renderFileIcon(file: File): React.ReactNode {
  const classNames = "h-3 w-3 mt-0.5";

  if (file.type.startsWith("image/")) {
    return <ImageIcon className={classNames} />;
  } else if (file.type.startsWith("text/")) {
    return <FileTextIcon className={classNames} />;
  }

  return <FileIcon className={classNames} />;
}
