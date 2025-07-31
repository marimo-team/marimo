/* Copyright 2024 Marimo. All rights reserved. */

import type { ReactNode } from "react";
import { Banner } from "@/plugins/impl/common/error-banner";
import { DelayMount } from "../../utils/delay-mount";

interface FloatingAlertProps {
  title?: string;
  children: ReactNode;
  show: boolean;
  delayMs?: number;
  kind?: "info" | "warn" | "danger";
}

export const FloatingAlert: React.FC<FloatingAlertProps> = ({
  title,
  children,
  show,
  delayMs = 2000,
  kind = "info",
}) => {
  if (!show) {
    return null;
  }

  const body = (
    <div className="flex flex-col gap-4 mb-5 fixed top-5 left-1/2 transform -translate-x-1/2 z-[200] opacity-95">
      <Banner
        kind={kind}
        className="flex flex-col rounded py-2 px-4 animate-in slide-in-from-top w-fit"
      >
        {title && (
          <div className="flex justify-between">
            <span className="font-bold text-lg flex items-center mb-1">
              {title}
            </span>
          </div>
        )}
        <div className="flex flex-col gap-4 justify-between items-start text-muted-foreground text-base">
          <div>{children}</div>
        </div>
      </Banner>
    </div>
  );

  return <DelayMount milliseconds={delayMs}>{body}</DelayMount>;
};
