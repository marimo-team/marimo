/* Copyright 2026 Marimo. All rights reserved. */

import type { HTMLProps, PropsWithChildren } from "react";
import type { SqlOutputType } from "@/core/config/config-schema";
import { cn } from "@/utils/cn";

export const formItemClasses =
  "settings-row flex flex-row items-center space-x-1 space-y-0";

export const SettingTitle: React.FC<PropsWithChildren> = ({ children }) => {
  return (
    <div className="text-md font-semibold text-muted-foreground uppercase tracking-wide  mb-1">
      {children}
    </div>
  );
};

export const SettingSubtitle: React.FC<HTMLProps<HTMLHeadingElement>> = ({
  children,
  className,
  ...props
}) => {
  return (
    <h3
      {...props}
      className={cn("text-sm font-semibold text-foreground", className)}
    >
      {children}
    </h3>
  );
};

export const SettingDescription: React.FC<PropsWithChildren> = ({
  children,
}) => {
  return <p className="text-sm text-muted-foreground">{children}</p>;
};

export const SettingGroup: React.FC<{
  title: string;
  children: React.ReactNode;
}> = ({ title, children }) => {
  return (
    <div className="settings-group flex flex-col gap-4">
      <SettingSubtitle>{title}</SettingSubtitle>
      {children}
    </div>
  );
};

export const SQL_OUTPUT_SELECT_OPTIONS: {
  label: string;
  value: SqlOutputType;
}[] = [
  { label: "Auto (Default)", value: "auto" },
  { label: "Native", value: "native" },
  { label: "Polars", value: "polars" },
  { label: "Lazy Polars", value: "lazy-polars" },
  { label: "Pandas", value: "pandas" },
];
