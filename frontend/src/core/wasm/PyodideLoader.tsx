/* Copyright 2026 Marimo. All rights reserved. */

import { useAtomValue } from "jotai";
import type React from "react";
import type { PropsWithChildren } from "react";
import { useEffect, useRef } from "react";
import { LargeSpinner } from "@/components/icons/large-spinner";
import { toast } from "@/components/ui/use-toast";
import { hasCellsAtom } from "@/core/cells/cells";
import { showCodeInRunModeAtom } from "@/core/meta/state";
import { store } from "@/core/state/jotai";
import { useAsyncData } from "@/hooks/useAsyncData";
import { prettyError } from "@/utils/errors";
import { Logger } from "@/utils/Logger";
import { hasQueryParam } from "@/utils/urls";
import { KnownQueryParams } from "../constants";
import { type AppMode, getInitialAppMode } from "../mode";
import { PyodideBridge } from "./bridge";
import { hasAnyOutputAtom, wasmInitializationAtom } from "./state";
import { isWasm } from "./utils";

/**
 * HOC to load Pyodide before rendering children, if necessary.
 */
export const PyodideLoader: React.FC<PropsWithChildren> = ({ children }) => {
  if (!isWasm()) {
    return children;
  }

  return <PyodideLoaderInner>{children}</PyodideLoaderInner>;
};

const PyodideLoaderInner: React.FC<PropsWithChildren> = ({ children }) => {
  // Don't block render on Pyodide: a hydrated snapshot can paint immediately
  // while Pyodide downloads in the background.
  const { error } = useAsyncData(async () => {
    await PyodideBridge.INSTANCE.initialized.promise;
    return true;
  }, []);

  const hasCells = useAtomValue(hasCellsAtom);
  const hasOutput = useAtomValue(hasAnyOutputAtom);
  const nothingToShow = shouldShowSpinner({
    hasCells,
    hasOutput,
    mode: getInitialAppMode(),
    codeHidden: isCodeHidden(),
  });

  const didToastErrorRef = useRef(false);
  useEffect(() => {
    // With snapshot content on-screen, toast instead of throwing so the
    // snapshot stays readable. The ref ensures we only toast once even if
    // nothingToShow toggles later.
    if (error && !nothingToShow && !didToastErrorRef.current) {
      didToastErrorRef.current = true;
      Logger.error("Pyodide failed to initialize", error);
      toast({
        title: "Failed to start the notebook runtime",
        description: prettyError(error),
        variant: "danger",
      });
    }
  }, [error, nothingToShow]);

  if (error && nothingToShow) {
    throw error;
  }

  if (nothingToShow) {
    return <WasmSpinner />;
  }

  return children;
};

function isCodeHidden() {
  // Code is hidden if ANY are true:
  // - the query param is set to false
  // - the view.showAppCode is false
  return (
    hasQueryParam(KnownQueryParams.showCode, "false") ||
    !store.get(showCodeInRunModeAtom)
  );
}

/**
 * Pure predicate: should the WASM loader render a spinner instead of its
 * children? We block render only when nothing user-visible would appear:
 *   - no cells have been hydrated (Pyodide hasn't parsed the notebook), or
 *   - we are in headless run mode (code hidden) with no outputs to display.
 */
export function shouldShowSpinner(input: {
  hasCells: boolean;
  hasOutput: boolean;
  mode: AppMode;
  codeHidden: boolean;
}): boolean {
  const { hasCells, hasOutput, mode, codeHidden } = input;
  if (!hasCells) {
    return true;
  }
  return !hasOutput && mode === "read" && codeHidden;
}

export const WasmSpinner: React.FC<PropsWithChildren> = ({ children }) => {
  const wasmInitialization = useAtomValue(wasmInitializationAtom);

  return <LargeSpinner title={wasmInitialization} />;
};
