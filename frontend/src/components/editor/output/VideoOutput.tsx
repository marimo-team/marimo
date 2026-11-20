/* Copyright 2026 Marimo. All rights reserved. */
import type { JSX } from "react";
import { useSanitizeHtml } from "@/plugins/core/sanitize";

interface Props {
  src: string;
  className?: string;
}

export const VideoOutput = ({ src, className }: Props): JSX.Element => {
  const shouldSanitize = useSanitizeHtml();
  if (shouldSanitize) {
    return <video className={className} src={src} controls={true} />;
  }
  // oxlint-disable-next-line react/iframe-missing-sandbox, react-doctor/iframe-missing-sandbox -- Trusted notebook output can include active documents.
  return <iframe className={className} src={src} title="Video output" />;
};
