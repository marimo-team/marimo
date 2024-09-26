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

/**
 * HOC to load Pyodide before rendering children, if necessary.
 */
export const PyodideLoader: React.FC<PropsWithChildren> = ({ children }) => {
  if (!isWasm()) {
    return children;
  }

  // isPyodide() is constant, so this is safe
  // eslint-disable-next-line react-hooks/rules-of-hooks
  const { loading, error } = useAsyncData(async () => {
    await PyodideBridge.INSTANCE.initialized.promise;
    return true;
  }, []);

  // eslint-disable-next-line react-hooks/rules-of-hooks
  const hasOutput = useAtomValue(hasAnyOutputAtom);

  if (loading) {
    return <WasmSpinner />;
  }

  // If we:
  // - are in read mode
  // - we are not showing the code
  // - and there is no output
  // then show the spinner
  if (
    !hasOutput &&
    initialMode === "read" &&
    hasQueryParam(KnownQueryParams.showCode, "false")
  ) {
    return <WasmSpinner />;
  }

  // Propagate back up to our error boundary
  if (error) {
    throw error;
  }

  return children;
};

export const WasmSpinner: React.FC<PropsWithChildren> = ({ children }) => {
  const wasmInitialization = useAtomValue(wasmInitializationAtom);

  return <LargeSpinner title={wasmInitialization} />;
};
