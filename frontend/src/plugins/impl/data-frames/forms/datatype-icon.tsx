/* Copyright 2026 Marimo. All rights reserved. */
import {
  BinaryIcon,
  BracesIcon,
  CalendarIcon,
  CaseSensitiveIcon,
  ToggleLeftIcon,
} from "lucide-react";
import React from "react";

interface Props {
  type: string;
}

export const DataTypeIcon: React.FC<Props> = ({ type }) => {
  const renderIcon = () => {
    if (
      type.startsWith("int") ||
      type.startsWith("float") ||
      type.startsWith("uint") ||
      type.startsWith("number") ||
      type.startsWith("complex")
    ) {
      return <BinaryIcon size={14} />;
    }
    if (type.startsWith("object") || type.startsWith("string")) {
      return <CaseSensitiveIcon size={14} />;
    }
    if (type.startsWith("date") || type.startsWith("time")) {
      return <CalendarIcon size={14} />;
    }
    if (type.startsWith("bool")) {
      return <ToggleLeftIcon size={14} />;
    }
    return <BracesIcon size={14} />;
  };

  return (
    <div className="border p-px border-border bg-(--slate-2) flex items-center justify-center rounded">
      {renderIcon()}
    </div>
  );
};
