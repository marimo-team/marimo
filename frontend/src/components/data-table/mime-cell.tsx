/* Copyright 2024 Marimo. All rights reserved. */
import { cn } from "@/utils/cn";
import { formatOutput } from "../editor/Output";
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
          channel: "output",
          data: value.data,
          mimetype: value.mimetype,
          timestamp: 0,
        } as OutputMessage,
      })}
    </div>
  );
};
