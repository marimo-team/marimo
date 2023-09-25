/* Copyright 2023 Marimo. All rights reserved. */
import { PropsWithChildren } from "react";

export const SettingTitle: React.FC<PropsWithChildren> = ({ children }) => {
  return (
    <div className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">
      {children}
    </div>
  );
};
