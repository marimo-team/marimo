import type { JSX } from "react";
/* Copyright 2024 Marimo. All rights reserved. */

interface Props {
  src: string;
  className?: string;
}

export const VideoOutput = ({ src, className }: Props): JSX.Element => {
  return (
    // eslint-disable-next-line jsx-a11y/iframe-has-title
    <iframe className={className} src={src} />
  );
};
