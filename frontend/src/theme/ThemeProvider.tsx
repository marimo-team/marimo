/* Copyright 2024 Marimo. All rights reserved. */
import { PropsWithChildren, memo, useLayoutEffect } from "react";
import { useTheme } from "./useTheme";

/**
 * Marimo's theme provider.
 */
export const ThemeProvider: React.FC<PropsWithChildren> = memo(
  ({ children }) => {
    const { theme } = useTheme();
    useLayoutEffect(() => {
      document.body.classList.add(theme, `${theme}-theme`);
      return () => {
        document.body.classList.remove(theme, `${theme}-theme`);
      };
    }, [theme]);

    return children;
  },
);
ThemeProvider.displayName = "ThemeProvider";

export const CssVariables: React.FC<{
  variables: Record<`--marimo-${string}`, string>;
  children: React.ReactNode;
}> = ({ variables, children }) => {
  return (
    <div className="contents" style={variables}>
      {children}
    </div>
  );
};
