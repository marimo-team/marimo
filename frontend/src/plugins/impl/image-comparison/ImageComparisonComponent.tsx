/* Copyright 2026 Marimo. All rights reserved. */

import { ImgComparisonSlider } from "@img-comparison-slider/react";
import React from "react";

export interface ImageComparisonData {
  beforeSrc: string;
  afterSrc: string;
  value: number;
  direction: "horizontal" | "vertical";
  width?: string;
  height?: string;
}

// Truncate long sources (e.g. base64 data URLs) so error messages stay
// readable.
function truncateSrc(src: string): string {
  const MAX_LENGTH = 100;
  return src.length > MAX_LENGTH ? `${src.slice(0, MAX_LENGTH)}…` : src;
}

const ImageComparisonComponent: React.FC<ImageComparisonData> = ({
  beforeSrc,
  afterSrc,
  value,
  direction,
  width,
  height,
}) => {
  const [failedSrcs, setFailedSrcs] = React.useState<ReadonlySet<string>>(
    () => new Set(),
  );

  React.useEffect(() => {
    setFailedSrcs(new Set());
  }, [beforeSrc, afterSrc]);

  const handleError = React.useCallback((src: string) => {
    setFailedSrcs((prev) => new Set(prev).add(src));
  }, []);

  const containerStyle: React.CSSProperties = {
    width: width || "100%",
    height: height || (direction === "vertical" ? "400px" : "auto"),
    maxWidth: "100%",
    // The slider derives its height entirely from its (loaded) images, so a
    // broken/slow-loading source would otherwise collapse it to nothing and
    // render an empty output. Keep a minimum height so it stays visible.
    minHeight: "2rem",
  };

  // If an image fails to load, the slider collapses to nothing; surface a
  // visible error instead of silently rendering an empty output.
  if (failedSrcs.size > 0) {
    return (
      <div
        style={containerStyle}
        className="flex items-center justify-center rounded border border-destructive/40 bg-destructive/5 p-3 text-sm text-destructive"
      >
        <span>
          Failed to load {failedSrcs.size > 1 ? "images" : "image"}:{" "}
          {[...failedSrcs].map((src) => `"${truncateSrc(src)}"`).join(", ")}
        </span>
      </div>
    );
  }

  return (
    <div style={containerStyle}>
      <ImgComparisonSlider value={value} direction={direction}>
        <img
          slot="first"
          src={beforeSrc}
          alt="Before"
          width="100%"
          onError={() => handleError(beforeSrc)}
        />
        <img
          slot="second"
          src={afterSrc}
          alt="After"
          width="100%"
          onError={() => handleError(afterSrc)}
        />
      </ImgComparisonSlider>
    </div>
  );
};

export default ImageComparisonComponent;
