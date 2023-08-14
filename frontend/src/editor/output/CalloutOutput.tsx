/* Copyright 2023 Marimo. All rights reserved. */
import { memo } from "react";
import { HtmlOutput } from "./HtmlOutput";
import { calloutStyles } from "./CalloutOutput.styles";

interface Props {
  html: string;
  kind: "neutral" | "alert" | "warn" | "success";
}

export const CalloutOutput: React.FC<Props> = memo(({ html, kind }) => {
  return (
    <div className={calloutStyles({ kind })}>
      <HtmlOutput html={html} />
    </div>
  );
});
CalloutOutput.displayName = "CalloutOutput";
