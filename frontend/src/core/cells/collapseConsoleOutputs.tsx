/* Copyright 2026 Marimo. All rights reserved. */
import {
  StatefulOutputMessage,
  type StringOutputMessage,
} from "@/components/editor/output/ansi-reduce";
import type { OutputMessage } from "@/core/kernel/messages";
import { invariant } from "@/utils/invariant";

/**
 * Collapses the last text/plain cells with the preceding one on the same
 * channel (if any), and handles bare carriage returns ("\r").
 */
export function collapseConsoleOutputs(
  consoleOutputs: OutputMessage[],
  maxLines = 5000,
): OutputMessage[] {
  const newConsoleOutputs = [...consoleOutputs];

  if (newConsoleOutputs.length < 2) {
    return truncateHead(
      newConsoleOutputs.map(maybeMakeOutputStateful),
      maxLines,
    );
  }

  const lastOutput = newConsoleOutputs[newConsoleOutputs.length - 1];
  const secondLastOutput = newConsoleOutputs[newConsoleOutputs.length - 2];

  if (shouldCollapse(lastOutput, secondLastOutput)) {
    assertStringOutputMessage(lastOutput);
    assertStringOutputMessage(secondLastOutput);

    newConsoleOutputs[newConsoleOutputs.length - 2] = mergeLeft(
      secondLastOutput,
      lastOutput,
    );
    newConsoleOutputs.pop();
  }

  return truncateHead(newConsoleOutputs, maxLines);
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

export function maybeMakeOutputStateful(output: OutputMessage): OutputMessage {
  if (output instanceof StatefulOutputMessage) {
    return output;
  }
  if (typeof output.data === "string") {
    return StatefulOutputMessage.create(output as StringOutputMessage);
  }
  return output;
}

function mergeLeft(
  first: StringOutputMessage | StatefulOutputMessage,
  second: StringOutputMessage,
): StatefulOutputMessage {
  if (first instanceof StatefulOutputMessage) {
    return first.appendData(second.data);
  }

  return StatefulOutputMessage.create(first).appendData(second.data);
}

function assertStringOutputMessage(
  output: OutputMessage,
): asserts output is StringOutputMessage {
  invariant(typeof output.data === "string", "expected string output");
}

function truncateHead(consoleOutputs: OutputMessage[], limit: number) {
  let nLines = 0;
  let i: number;
  for (i = consoleOutputs.length - 1; i >= 0 && nLines < limit; i--) {
    const output: OutputMessage = consoleOutputs[i];
    if (output.mimetype === "text/plain") {
      invariant(typeof output.data === "string", "expected string");
      nLines += output.data.split("\n").length;
    } else {
      nLines++;
    }
  }

  if (nLines < limit) {
    return consoleOutputs;
  }

  const cutoff = i + 1;
  const warningOutput: OutputMessage = {
    channel: "stderr",
    mimetype: "text/html",
    data: `<pre>Streaming output truncated to last ${limit} lines.\n</pre>`,
    timestamp: -1,
  };
  const output = consoleOutputs[cutoff];
  if (output.mimetype === "text/plain") {
    invariant(typeof output.data === "string", "expected string");
    const outputLines = output.data.split("\n");
    const nLinesAfterOutput = nLines - outputLines.length;
    const nLinesToKeep = limit - nLinesAfterOutput;
    return [
      warningOutput,
      { ...output, data: outputLines.slice(-nLinesToKeep).join("\n") },
      ...consoleOutputs.slice(cutoff + 1),
    ];
  }
  return [warningOutput, ...consoleOutputs.slice(cutoff + 1)];
}
