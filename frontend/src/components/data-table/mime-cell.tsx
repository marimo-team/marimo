/* Copyright 2024 Marimo. All rights reserved. */
import { cn } from "@/utils/cn";
import { OutputRenderer } from "../editor/Output";
import type { OutputMessage } from "@/core/kernel/messages";

interface MimeCellProps {
  value: MimeValue;
}

interface MimeValue {
  mimetype: string;
  data: string;
}

export const MimeCell = ({ value }: MimeCellProps) => {
  const message = {
    channel: "output",
    data: value.data,
    mimetype: value.mimetype,
    timestamp: 0,
  } as OutputMessage;

  return (
    <div className={cn("flex items-center space-x-2")}>
      <OutputRenderer message={message} />
    </div>
  );
};

export function isMimeValue(value: unknown): value is MimeValue {
  return (
    typeof value === "object" &&
    value !== null &&
    "mimetype" in value &&
    "data" in value
  );
}
