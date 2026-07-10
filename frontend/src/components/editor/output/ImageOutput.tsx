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
  // Numeric dimensions are set as HTML attributes rather than inline styles.
  // Attributes give the browser the image's intrinsic size and aspect ratio,
  // but can still be overridden by stylesheet rules (`max-width: 100%;
  // height: auto` from preflight), so images shrink proportionally in
  // width-constrained containers like mo.hstack. Inline styles would win
  // over `height: auto` and distort the aspect ratio.
  //
  // String values like "100%" are only valid in CSS, so they go in the
  // style attribute.
  const style: React.CSSProperties = {};
  if (typeof width === "string") {
    style.width = width;
  }
  if (typeof height === "string") {
    style.height = height;
  }

  return (
    <span className={className}>
      <img
        src={src}
        alt={alt}
        width={typeof width === "number" ? width : undefined}
        height={typeof height === "number" ? height : undefined}
        style={style}
      />
    </span>
  );
};
