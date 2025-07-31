/* Copyright 2024 Marimo. All rights reserved. */
import React from "react";

interface Props {
  title: string;
  description?: React.ReactNode;
  icon?: React.ReactElement<{ className?: string }>;
  action?: React.ReactNode;
}

export const PanelEmptyState = ({
  title,
  description,
  icon,
  action,
}: Props) => {
  return (
    <div className="mx-6 my-6 flex flex-col gap-2">
      <div className="flex flex-row gap-2 items-center">
        {icon &&
          React.cloneElement(icon, { className: "text-accent-foreground" })}
        <span className="mt-1 text-accent-foreground">{title}</span>
      </div>
      <span className="text-muted-foreground text-sm">{description}</span>
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
};
