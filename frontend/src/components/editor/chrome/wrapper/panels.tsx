/* Copyright 2024 Marimo. All rights reserved. */
import type { PropsWithChildren } from "react";

export const PanelsWrapper: React.FC<PropsWithChildren> = ({ children }) => {
  return (
    <div className="flex flex-col flex-1 overflow-hidden absolute inset-0 print:relative">
      {children}
    </div>
  );
};
