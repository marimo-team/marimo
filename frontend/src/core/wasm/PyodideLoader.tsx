/* Copyright 2026 Marimo. All rights reserved. */

import { useAtomValue } from "jotai";
import type React from "react";
import type { PropsWithChildren } from "react";
import { useEffect, useRef } from "react";
import { LargeSpinner } from "@/components/icons/large-spinner";
import { ProgressiveBoundary } from "@/components/lifecycle/ProgressiveBoundary";
import { toast } from "@/components/ui/use-toast";
import { canPaintAtom } from "@/core/lifecycle/render-policy";
import { wasmInitStateAtom } from "@/core/wasm/state";
import { useAsyncData } from "@/hooks/useAsyncData";
import { prettyError } from "@/utils/errors";
import { Logger } from "@/utils/Logger";
import { PyodideBridge } from "./bridge";
import { isWasm } from "./utils";

/**
 * Paints the snapshot (or hydrated cells) immediately and lets Pyodide
 * finish downloading in the background. UI elements aren't interactive
 * until Pyodide is ready.
 */
export const PyodideLoader: React.FC<PropsWithChildren> = ({ children }) => {
  if (!isWasm()) {
    return children;
  }
  return <PyodideLoaderInner>{children}</PyodideLoaderInner>;
};

const PyodideLoaderInner: React.FC<PropsWithChildren> = ({ children }) => {
  const { error } = useAsyncData(async () => {
    await PyodideBridge.INSTANCE.initialized.promise;
    return true;
  }, []);

  const canPaint = useAtomValue(canPaintAtom);

  // If the snapshot is already on screen, toast instead of throwing so we
  // don't tear it down. With nothing painted, throw to surface the error UI.
  const didToastErrorRef = useRef(false);
  useEffect(() => {
    if (error && canPaint && !didToastErrorRef.current) {
      didToastErrorRef.current = true;
      Logger.error("Pyodide failed to initialize", error);
      toast({
        title: "Failed to start the notebook runtime",
        description: prettyError(error),
        variant: "danger",
      });
    }
  }, [error, canPaint]);

  if (error && !canPaint) {
    throw error;
  }

  return (
    <ProgressiveBoundary requires={canPaintAtom} fallback={<WasmSpinner />}>
      {children}
    </ProgressiveBoundary>
  );
};

const WasmSpinner: React.FC = () => {
  const state = useAtomValue(wasmInitStateAtom);
  const title = state.kind === "loading" ? state.message : "Loading…";
  return <LargeSpinner title={title} />;
};
