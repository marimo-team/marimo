/* Copyright 2024 Marimo. All rights reserved. */
import React, { PropsWithChildren } from "react";
import { useAsyncData } from "@/hooks/useAsyncData";
import { isPyodide } from "./utils";
import { PyodideBridge } from "./bridge";
import { LargeSpinner } from "@/components/icons/large-spinner";

/**
 * HOC to load Pyodide before rendering children, if necessary.
 */
export const PyodideLoader: React.FC<PropsWithChildren> = ({ children }) => {
  if (!isPyodide()) {
    return children;
  }

  // isPyodide() is constant, so this is safe
  // eslint-disable-next-line react-hooks/rules-of-hooks
  const { loading, error } = useAsyncData(async () => {
    await PyodideBridge.INSTANCE.initialized.promise;
    return true;
  }, []);

  if (loading) {
    return <LargeSpinner />;
  }

  // Propagate back up to our error boundary
  if (error) {
    throw error;
  }

  return children;
};
