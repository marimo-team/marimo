/* Copyright 2024 Marimo. All rights reserved. */
import type { JSX } from "react";

interface Props {
  src: string;
  className?: string;
}

export const VideoOutput = ({ src, className }: Props): JSX.Element => {
  return <iframe className={className} src={src} />;
};
