/* Copyright 2024 Marimo. All rights reserved. */
import React, { PropsWithChildren } from "react";

import "./multi-icon.css";

interface MultiIconProps {
  layerTop?: boolean;
}

/**
 * By default, first icon is left untouched, and second icon is layered to the
 * bottom right. When `layerTop`, second icon is layered to the top left.
 */
export const MultiIcon = ({
  children,
  layerTop = false,
}: PropsWithChildren<MultiIconProps>) => {
  const [first, second] = React.Children.toArray(children);
  const positioning = layerTop
    ? "top-[-1px] left-[-1px]"
    : "bottom-[-1px] right-[-1px]";
  return (
    <div className="multi-icon relative w-fit">
      {first}
      <div className={`second-icon absolute ${positioning} rounded-full`}>
        {second}
      </div>
    </div>
  );
};
