/* Copyright 2024 Marimo. All rights reserved. */
import React from "react";

interface Props {
  left?: React.ReactNode;
  center?: React.ReactNode;
  right?: React.ReactNode;
}

/**
 * Layout elements for toolbar.
 * This is better than justify-between since it handles adding/removing items.
 */
export const Toolbar: React.FC<Props> = (props) => {
  return (
    <div className="flex items-center gap-2 w-full px-3">
      <div className="flex-1 flex item-center gap-2">{props.left}</div>
      <div className="flex-1 flex item-center gap-2 justify-center">
        {props.center}
      </div>
      <div className="flex-1 flex item-center gap-2 justify-end">
        {props.right}
      </div>
    </div>
  );
};
