/* Copyright 2024 Marimo. All rights reserved. */
import React from "react";

interface Props {
  title: string;
  description?: React.ReactNode;
  color?: string;
  icon?: React.ReactElement;
}

export const PanelEmptyState = ({ title, description, color, icon }: Props) => {
  return (
    <div className="mx-6 my-6 flex flex-col gap-2">
      <div className="flex flex-row gap-2 items-center">
        {icon &&
          React.cloneElement(icon, { className: "text-accent-foreground" })}
        <span className="mt-1 text-accent-foreground">{title}</span>
      </div>
      <span className="text-muted-foreground text-sm">{description}</span>
    </div>
  );
};
