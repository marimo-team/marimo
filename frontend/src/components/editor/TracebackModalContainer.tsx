/* Copyright 2024 Marimo. All rights reserved. */
import React from "react";
import { useAtom } from "jotai";
import { tracebackModalAtom } from "@/core/errors/traceback-atom";
import { TracebackModal } from "./errors/traceback-modal";

export const TracebackModalContainer: React.FC = () => {
  const [tracebackData, setTracebackData] = useAtom(tracebackModalAtom);

  if (!tracebackData) {
    return null;
  }

  return (
    <TracebackModal
      isOpen={true}
      onClose={() => setTracebackData(null)}
      traceback={tracebackData.traceback}
      errorMessage={tracebackData.errorMessage}
    />
  );
};
