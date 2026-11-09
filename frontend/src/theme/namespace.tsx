/* Copyright 2026 Marimo. All rights reserved. */
import React, { type PropsWithChildren } from "react";
import { useTheme } from "./useTheme";

const style = {
  display: "contents",
};

/**
 * Scopes styles and applies the theme before descendants inherit text colors.
 */
export const StyleNamespace = React.forwardRef<
  HTMLDivElement,
  PropsWithChildren<{}>
>(({ children }, ref) => {
  const { theme } = useTheme();
  return (
    <div ref={ref} className={`marimo ${theme}`} style={style}>
      {children}
    </div>
  );
});

StyleNamespace.displayName = "StyleNamespace";
