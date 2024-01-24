/* Copyright 2024 Marimo. All rights reserved. */
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
      type.startsWith("complex")
    ) {
      return <BinaryIcon size={14} />;
    }
    if (type.startsWith("object")) {
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
    <div className="border p-[1px] border-border bg-[var(--slate-2)] flex items-center justify-center rounded">
      {renderIcon()}
    </div>
  );
};
