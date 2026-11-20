/* Copyright 2026 Marimo. All rights reserved. */
import {
  StatefulOutputMessage,
  type StringOutputMessage,
} from "@/components/editor/output/ansi-reduce";
import type { ConsoleOutputMessage as OutputMessage } from "./types";
import { invariant } from "@/utils/invariant";

const MAX_CONSOLE_LINES = 5000;

/** Merge the last write with the preceding row when both use the same text channel. */
export function collapseConsoleOutputs(
  consoleOutputs: OutputMessage[],
  maxLines = MAX_CONSOLE_LINES,
): OutputMessage[] {
  const outputs = consoleOutputs.slice(0, -1);
  const last = consoleOutputs.at(-1);
  if (last) {
    appendOutput(outputs, last);
  }
  return truncateHead(outputs, maxLines);
}

/** Rebuild the visible rows from a replay, carrying ANSI state across adjacent writes. */
export function collapseConsoleBatch(
  entries: OutputMessage[],
): OutputMessage[] {
  const rows: OutputMessage[] = [];
  for (let start = 0; start < entries.length;) {
    const first = entries[start];
    let end = start + 1;
    while (end < entries.length && shouldCollapse(first, entries[end])) {
      end++;
    }
    if (end === start + 1) {
      appendOutput(rows, first);
    } else {
      const text = entries.slice(start, end).map((entry) => {
        assertStringOutputMessage(entry);
        return entry.data;
      });
      rows.push(
        StatefulOutputMessage.create({ ...first, data: text.join("") }),
      );
    }
    start = end;
  }
  return truncateHead(rows, MAX_CONSOLE_LINES);
}

function appendOutput(outputs: OutputMessage[], entry: OutputMessage): void {
  const last = outputs.at(-1);
  if (last && shouldCollapse(last, entry)) {
    assertStringOutputMessage(last);
    assertStringOutputMessage(entry);
    outputs[outputs.length - 1] = mergeLeft(last, entry);
  } else {
    outputs.push(maybeMakeOutputStateful(entry));
  }
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
  if (
    output.mimetype === "text/plain" &&
    output.channel !== "stdin" &&
    typeof output.data === "string"
  ) {
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
      nLines +=
        output instanceof StatefulOutputMessage
          ? output.lineCount
          : output.data.split("\n").length;
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
  const pending = consoleOutputs
    .slice(0, cutoff)
    .filter((row) => row.channel === "stdin" && row.response === undefined);
  const retained = [warningOutput, ...pending];
  const output = consoleOutputs[cutoff];
  if (output?.channel === "stdin" && output.response === undefined) {
    return [...retained, ...consoleOutputs.slice(cutoff)];
  }
  if (output?.mimetype === "text/plain") {
    invariant(typeof output.data === "string", "expected string");
    const dropLines = nLines - limit;
    const tail =
      output instanceof StatefulOutputMessage
        ? output.dropFirstLines(dropLines)
        : {
            ...output,
            data: output.data.split("\n").slice(dropLines).join("\n"),
          };
    return [...retained, tail, ...consoleOutputs.slice(cutoff + 1)];
  }
  return [...retained, ...consoleOutputs.slice(cutoff + 1)];
}
