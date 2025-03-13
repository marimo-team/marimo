/* Copyright 2024 Marimo. All rights reserved. */
import type React from "react";
import type { PropsWithChildren } from "react";
import { useAsyncData } from "@/hooks/useAsyncData";
import { isWasm } from "./utils";
import { PyodideBridge } from "./bridge";
import { LargeSpinner } from "@/components/icons/large-spinner";
import { useAtomValue } from "jotai";
import { hasAnyOutputAtom, wasmInitializationAtom } from "./state";
import { initialMode } from "../mode";
import { hasQueryParam } from "@/utils/urls";
import { KnownQueryParams } from "../constants";
import { getMarimoShowCode } from "../dom/marimo-tag";

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
  // isPyodide() is constant, so this is safe
  const { loading, error } = useAsyncData(async () => {
    await PyodideBridge.INSTANCE.initialized.promise;
    return true;
  }, []);

  const hasOutput = useAtomValue(hasAnyOutputAtom);

  if (loading) {
    return <WasmSpinner />;
  }

  // If we:
  // - are in read mode
  // - we are not showing the code
  // - and there is no output
  // then show the spinner
  if (!hasOutput && initialMode === "read" && isCodeHidden()) {
    return <WasmSpinner />;
  }

  // Propagate back up to our error boundary
  if (error) {
    throw error;
  }

  return children;
};

function isCodeHidden() {
  // Code is hidden if:
  // - the query param is set to false
  // - the marimo-code html-tag has data-show-code="false"
  return (
    hasQueryParam(KnownQueryParams.showCode, "false") || !getMarimoShowCode()
  );
}

export const WasmSpinner: React.FC<PropsWithChildren> = ({ children }) => {
  const wasmInitialization = useAtomValue(wasmInitializationAtom);

  return <LargeSpinner title={wasmInitialization} />;
};
