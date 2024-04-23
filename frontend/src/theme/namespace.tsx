/* Copyright 2024 Marimo. All rights reserved. */
import React, { PropsWithChildren } from "react";

const style = {
  display: "contents",
};

/**
 * Adds the 'marimo' className which serves as a namespace to its children,
 * so that the styles are scoped to the DOM subtree.
 */
export const StyleNamespace: React.FC<PropsWithChildren> = ({ children }) => {
  return (
    <div className="marimo" style={style}>
      {children}
    </div>
  );
};
