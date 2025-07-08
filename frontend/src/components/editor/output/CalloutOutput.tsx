/* Copyright 2024 Marimo. All rights reserved. */
import { memo } from "react";
import type { Intent } from "@/plugins/impl/common/intent";
import { calloutStyles } from "./CalloutOutput.styles";
import { HtmlOutput } from "./HtmlOutput";

interface Props {
  html: string;
  kind: Intent;
}

export const CalloutOutput: React.FC<Props> = memo(({ html, kind }) => {
  return (
    <div className={calloutStyles({ kind })}>
      <HtmlOutput html={html} />
    </div>
  );
});
CalloutOutput.displayName = "CalloutOutput";
