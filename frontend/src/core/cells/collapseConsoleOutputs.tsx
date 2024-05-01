/* Copyright 2024 Marimo. All rights reserved. */
import { OutputMessage } from "@/core/kernel/messages";
import { invariant } from "@/utils/invariant";

/**
 * Collapses the last text/plain cells with the preceding one on the same
 * channel (if any), and handles bare carriage returns ("\r").
 */
export function collapseConsoleOutputs(
  consoleOutputs: OutputMessage[],
): OutputMessage[] {
  const newConsoleOutputs = [...consoleOutputs];

  if (newConsoleOutputs.length < 2) {
    return handleCarriageReturns(newConsoleOutputs);
  }

  const lastOutput = newConsoleOutputs[newConsoleOutputs.length - 1];
  const secondLastOutput = newConsoleOutputs[newConsoleOutputs.length - 2];

  if (shouldCollapse(lastOutput, secondLastOutput)) {
    invariant(typeof lastOutput.data === "string", "expected string");
    invariant(typeof secondLastOutput.data === "string", "expected string");

    secondLastOutput.data += lastOutput.data;
    newConsoleOutputs.pop();
  }

  return handleCarriageReturns(newConsoleOutputs);
}

function shouldCollapse(
  lastOutput: OutputMessage,
  secondLastOutput: OutputMessage,
): boolean {
  const isTextPlain =
    lastOutput.mimetype === "text/plain" &&
    secondLastOutput.mimetype === "text/plain";
  if (!isTextPlain) {
    return false;
  }
  const isSameChannel = lastOutput.channel === secondLastOutput.channel;
  const isNotStdin = lastOutput.channel !== "stdin";

  return isTextPlain && isSameChannel && isNotStdin;
}
function handleCarriageReturns(
  consoleOutputs: OutputMessage[],
): OutputMessage[] {
  const newConsoleOutputs = [...consoleOutputs];
  if (newConsoleOutputs.length === 0) {
    return newConsoleOutputs;
  }

  const lastOutput = newConsoleOutputs[newConsoleOutputs.length - 1];
  if (lastOutput.mimetype !== "text/plain") {
    return newConsoleOutputs;
  }

  // eslint-disable-next-line no-control-regex
  const carriagePattern = new RegExp("\r[^\n]", "g");
  // collapse carriage returns in the final output's data
  let text = lastOutput.data;
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

  newConsoleOutputs[newConsoleOutputs.length - 1] = { ...lastOutput, data: text };
  return newConsoleOutputs;
}
