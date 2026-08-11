/* Copyright 2026 Marimo. All rights reserved. */

import React from "react";
import { Spinner } from "@/components/icons/spinner";

const LazyProfilingPanel = React.lazy(() =>
  import("@/components/profiling/profiling-panel").then((module) => {
    return {
      default: module.ProfilingPanel,
    };
  }),
);

const ProfilingPanel: React.FC = () => {
  return (
    <React.Suspense fallback={<Loading />}>
      <LazyProfilingPanel />
    </React.Suspense>
  );
};

export default ProfilingPanel;

const Loading = () => {
  return (
    <div className="flex flex-col items-center justify-center h-full">
      <Spinner />
    </div>
  );
};
