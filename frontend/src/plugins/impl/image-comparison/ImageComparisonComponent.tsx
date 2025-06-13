/* Copyright 2024 Marimo. All rights reserved. */

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

const ImageComparisonComponent: React.FC<ImageComparisonData> = ({
  beforeSrc,
  afterSrc,
  value,
  direction,
  width,
  height,
}) => {
  const containerStyle: React.CSSProperties = {
    width: width || "100%",
    height: height || (direction === "vertical" ? "400px" : "auto"),
    maxWidth: "100%",
  };

  return (
    <div style={containerStyle}>
      <ImgComparisonSlider value={value} direction={direction}>
        <img slot="first" src={beforeSrc} alt="Before" width="100%" />
        <img slot="second" src={afterSrc} alt="After" width="100%" />
      </ImgComparisonSlider>
    </div>
  );
};

export default ImageComparisonComponent;
