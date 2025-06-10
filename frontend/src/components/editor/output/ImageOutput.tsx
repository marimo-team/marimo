/* Copyright 2024 Marimo. All rights reserved. */

import type { JSX } from "react";

interface Props {
  src: string;
  alt?: string;
  width?: number;
  height?: number;
  className?: string;
}

export const ImageOutput = ({
  src,
  alt = "",
  width,
  height,
  className,
}: Props): JSX.Element => {
  return (
    <span className={className}>
      <img src={src} alt={alt} width={width} height={height} />
    </span>
  );
};
