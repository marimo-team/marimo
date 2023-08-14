/* Copyright 2023 Marimo. All rights reserved. */
import { cn } from "@/lib/utils";
import { formatOutput } from "../../editor/Output";
import { OutputMessage } from "../../core/kernel/messages";

interface MimeCellProps {
  value: unknown;
}

export const MimeCell = ({ value }: MimeCellProps) => {
  if (typeof value !== "object" || value === null) {
    return null;
  }

  if (!("mimetype" in value && "data" in value)) {
    return null;
  }

  return (
    <div className={cn("flex items-center space-x-2")}>
      {formatOutput({
        message: {
          channel: "",
          data: value.data,
          mimetype: value.mimetype,
          timestamp: "",
        } as OutputMessage,
      })}
    </div>
  );
};
