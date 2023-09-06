/* Copyright 2023 Marimo. All rights reserved. */
import React, { PropsWithChildren } from "react";

/**
 * First icon is left untouched, and second icon is layered to the bottom right/
 */
export const MultiIcon = (props: PropsWithChildren) => {
  const [first, second] = React.Children.toArray(props.children);
  return (
    <div className="relative">
      {first}
      <div className="absolute bottom-0 right-1 transform translate-x-1/2 translate-y-1/2">
        {second}
      </div>
    </div>
  );
};
