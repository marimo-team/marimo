/* Copyright 2026 Marimo. All rights reserved. */

import type { JSX } from "react";

interface Props {
  src: string;
  alt?: string;
  width?: number | string;
  height?: number | string;
  className?: string;
}

export const ImageOutput = ({
  src,
  alt = "",
  width,
  height,
  className,
}: Props): JSX.Element => {
  // Convert numeric values to pixel strings, pass string values (like "100%") as-is
  const style: React.CSSProperties = {};
  if (width !== undefined) {
    style.width = typeof width === "number" ? `${width}px` : width;
  }
  if (height !== undefined) {
    style.height = typeof height === "number" ? `${height}px` : height;
  }

  return (
    <span className={className}>
      <img src={src} alt={alt} style={style} />
    </span>
  );
};
