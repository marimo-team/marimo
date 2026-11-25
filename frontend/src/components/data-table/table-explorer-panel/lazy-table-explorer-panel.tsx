/* Copyright 2026 Marimo. All rights reserved. */

import { lazy, Suspense, useState } from "react";
import { ErrorBoundary } from "react-error-boundary";
import { Button } from "@/components/ui/button";
import { reactLazyWithPreload } from "@/utils/lazy";
import type { TableExplorerPanelProps } from "./table-explorer-panel";

const explorer = reactLazyWithPreload<TableExplorerPanelProps<unknown>>(() =>
  import("./table-explorer-panel").then((mod) => ({
    default: mod.TableExplorerPanel,
  })),
);

export const LazyTableExplorerPanel = (
  props: TableExplorerPanelProps<unknown>,
) => {
  const [Component, setComponent] = useState(() => lazy(explorer.preload));

  return (
    <ErrorBoundary
      onReset={() => {
        // React.lazy caches rejections, so retries need a fresh component.
        setComponent(() => lazy(explorer.preload));
      }}
      fallbackRender={({ resetErrorBoundary }) => (
        <div className="p-4 flex flex-col items-start gap-2">
          Could not load the explorer.
          <Button variant="outline" onClick={resetErrorBoundary}>
            Try again
          </Button>
        </div>
      )}
    >
      <Suspense
        fallback={
          <div className="p-4 text-muted-foreground">Loading explorer...</div>
        }
      >
        <Component {...props} />
      </Suspense>
    </ErrorBoundary>
  );
};
