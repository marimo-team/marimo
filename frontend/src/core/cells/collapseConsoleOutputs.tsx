/* Copyright 2024 Marimo. All rights reserved. */
import { OutputMessage } from "@/core/kernel/messages";

// collapses the last text/plain cells with the preceding one on the same
// channel (if any), and handles bare carriage returns ("\r")
export function collapseConsoleOutputs(
  consoleOutputs: OutputMessage[],
): OutputMessage[] {
  let nextOutput = consoleOutputs[consoleOutputs.length - 1];
  if (nextOutput.mimetype !== "text/plain") {
    return consoleOutputs;
  }

  // Skip stdin
  if (
    consoleOutputs.length >= 2 &&
    consoleOutputs[consoleOutputs.length - 2].mimetype === "text/plain" &&
    consoleOutputs[consoleOutputs.length - 2].channel === nextOutput.channel &&
    nextOutput.channel !== "stdin"
  ) {
    consoleOutputs.pop();
    // eslint-disable-next-line @typescript-eslint/restrict-plus-operands
    consoleOutputs[consoleOutputs.length - 1].data += nextOutput.data;
    nextOutput = consoleOutputs[consoleOutputs.length - 1];
  }

  if (nextOutput.mimetype !== "text/plain") {
    return consoleOutputs;
  }

  // eslint-disable-next-line no-control-regex
  const carriagePattern = new RegExp("\r[^\n]", "g");
  // collapse carriage returns in the final output's data
  let text = nextOutput.data;
  let carriageIdx = text.search(carriagePattern);
  while (carriageIdx > -1) {
    // find the newline character preceding the carriage return, if any
    let newlineIdx = -1;
    for (let i = carriageIdx - 1; i >= 0; i--) {
      if (text.at(i) === "\n") {
        newlineIdx = i;
        break;
      }
    }
    const postCarriageText = text.slice(carriageIdx + 1);
    const prefix = text.slice(0, newlineIdx + 1);
    const intermediateText = text.slice(newlineIdx + 1, carriageIdx);
    text =
      intermediateText.length <= postCarriageText.length
        ? prefix + postCarriageText
        : prefix +
          postCarriageText +
          intermediateText.slice(postCarriageText.length);
    carriageIdx = text.search(carriagePattern);
  }

  consoleOutputs[consoleOutputs.length - 1].data = text;
  return consoleOutputs;
}
