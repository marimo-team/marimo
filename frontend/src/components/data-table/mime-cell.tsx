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

export function getMimeValues(value: unknown): MimeValue[] | undefined {
  if (isMimeValue(value)) {
    return [value];
  }

  const hasSerializedMimeBundle =
    typeof value === "object" &&
    value !== null &&
    "serialized_mime_bundle" in value;

  if (hasSerializedMimeBundle) {
    const serializedMimeBundle = value.serialized_mime_bundle;
    if (isMimeValue(serializedMimeBundle)) {
      return [serializedMimeBundle];
    }
  }

  // can also be a list of mime values
  // only return if all values are mime values
  // TODO: Maybe support mixed mime values and non-mime values
  if (Array.isArray(value)) {
    const allMimeType = value.every(isMimeValue);
    if (allMimeType) {
      return value.map((v) => v);
    }
  }
}
