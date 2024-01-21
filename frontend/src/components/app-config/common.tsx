/* Copyright 2024 Marimo. All rights reserved. */
import { PropsWithChildren } from "react";

export const SettingTitle: React.FC<PropsWithChildren> = ({ children }) => {
  return (
    <div className="text-sm font-semibold text-muted-foreground uppercase tracking-wide  mb-1">
      {children}
    </div>
  );
};

export const SettingSubtitle: React.FC<PropsWithChildren> = ({ children }) => {
  return (
    <div className="text-sm font-semibold underline decoration-solid decoration-gray-400 underline-offset-2 text-muted-foreground uppercase tracking-wide">
      {children}
    </div>
  );
};

export const SettingDescription: React.FC<PropsWithChildren> = ({
  children,
}) => {
  return <p className="text-sm text-muted-foreground">{children}</p>;
};
