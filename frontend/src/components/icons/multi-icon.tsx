/* Copyright 2023 Marimo. All rights reserved. */
import React, { PropsWithChildren } from "react";

import "./multi-icon.css";

/**
 * First icon is left untouched, and second icon is layered to the bottom right/
 */
export const MultiIcon = ({ children }: PropsWithChildren) => {
  const [first, second] = React.Children.toArray(children);
  return (
    <div className="multi-icon relative w-fit">
      {first}
      <div
        className={
          "second-icon absolute bottom-[-1px] right-[-1px] rounded-full"
        }
      >
        {second}
      </div>
    </div>
  );
};
