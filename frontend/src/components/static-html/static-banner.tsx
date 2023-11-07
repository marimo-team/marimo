/* Copyright 2023 Marimo. All rights reserved. */
import { isStaticNotebook } from "@/core/static/static-state";
import React from "react";

export const StaticBanner: React.FC = () => {
  if (!isStaticNotebook()) {
    return null;
  }

  return (
    <div className="px-4 py-2 bg-[var(--sky-2)] border-b border-[var(--sky-7)] text-sm text-[var(--sky-11)] font-semibold">
      This is a static notebook. Any interactive features will not work.
    </div>
  );
};
