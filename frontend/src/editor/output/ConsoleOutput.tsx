/* Copyright 2023 Marimo. All rights reserved. */
import React from "react";
import { OutputMessage } from "@/core/kernel/messages";
import { formatOutput } from "../Output";
import { cn } from "@/lib/utils";

interface Props {
  consoleOutputs: OutputMessage[];
  stale: boolean;
}

export const ConsoleOutput = (props: Props): React.ReactNode => {
  const { consoleOutputs, stale } = props;
  if (consoleOutputs.length === 0) {
    return null;
  }

  return (
    <div
      title={stale ? "This console output is stale" : undefined}
      className={cn("console-output-area", stale && "marimo-output-stale")}
    >
      {consoleOutputs.map((output) => formatOutput({ message: output }))}
    </div>
  );
};
