/* Copyright 2024 Marimo. All rights reserved. */
import { memo } from "react";
import { renderHTML } from "../../../plugins/core/RenderHTML";
import { cn } from "../../../utils/cn";

interface Props {
  html: string;
  inline?: boolean;
  className?: string;
}

export const HtmlOutput: React.FC<Props> = memo(
  ({ html, inline = false, className }) => {
    if (!html) {
      return null;
    }

    return (
      <div className={cn(className, { "inline-flex": inline, block: !inline })}>
        {renderHTML({ html })}
      </div>
    );
  },
);
HtmlOutput.displayName = "HtmlOutput";
