/* Copyright 2024 Marimo. All rights reserved. */
import React, { type PropsWithChildren } from "react";

const style = {
  display: "contents",
};

/**
 * Adds the 'marimo' className which serves as a namespace to its children,
 * so that the styles are scoped to the DOM subtree.
 */
export const StyleNamespace = React.forwardRef<
  HTMLDivElement,
  PropsWithChildren<{}>
>(({ children }, ref) => {
  return (
    <div ref={ref} className="marimo" style={style}>
      {children}
    </div>
  );
});

StyleNamespace.displayName = "StyleNamespace";
