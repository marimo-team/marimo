/* Copyright 2024 Marimo. All rights reserved. */

import React from "react";
import { Spinner } from "@/components/icons/spinner";

const LazyTracing = React.lazy(() =>
  import("@/components/tracing/tracing").then((module) => {
    return {
      default: module.Tracing,
    };
  }),
);

export const TracingPanel: React.FC = () => {
  return (
    <React.Suspense fallback={<Loading />}>
      <LazyTracing />
    </React.Suspense>
  );
};

const Loading = () => {
  return (
    <div className="flex flex-col items-center justify-center h-full">
      <Spinner />
    </div>
  );
};
