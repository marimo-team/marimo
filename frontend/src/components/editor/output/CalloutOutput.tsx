/* Copyright 2026 Marimo. All rights reserved. */
import { memo } from "react";
import type { Intent } from "@/plugins/impl/common/intent";
import { cn } from "@/utils/cn";
import { HtmlOutput } from "./HtmlOutput";

interface Props {
  html: string;
  kind: Intent;
  title?: string;
}

// Callouts share the flat admonition style of markdown admonitions
// (css/admonition.css); each intent maps onto an admonition kind.
const KIND_CLASS: Record<Intent, string> = {
  neutral: "neutral",
  info: "info",
  warn: "warning",
  success: "success",
  danger: "danger",
  // 'alert' is deprecated; render as danger
  alert: "danger",
};

export const CalloutOutput: React.FC<Props> = memo(({ html, kind, title }) => {
  return (
    <div className={cn("admonition", KIND_CLASS[kind])}>
      {title && <span className="admonition-title">{title}</span>}
      <HtmlOutput html={html} alwaysSanitizeHtml={true} />
    </div>
  );
});
CalloutOutput.displayName = "CalloutOutput";
