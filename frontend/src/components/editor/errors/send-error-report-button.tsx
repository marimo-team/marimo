/* Copyright 2026 Marimo. All rights reserved. */

import { useAtomValue, useStore } from "jotai";
import { SendIcon } from "lucide-react";
import { useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { toast } from "@/components/ui/use-toast";
import { notebookAtom } from "@/core/cells/cells";
import type { CellId } from "@/core/cells/ids";
import { pairPreviewAtom } from "@/core/config/pair";
import { API } from "@/core/network/api";
import { participantPresenceAtom } from "@/core/participants/state";
import { sanitizeHtml } from "@/plugins/core/sanitize-html";

interface HandoffPayload {
  cellId: string;
  error: string;
  code: string;
  traceback: string;
  consoleTail: { channel: "stdout" | "stderr"; data: string }[];
}

const MAX_CONSOLE_LINES = 20;
const MAX_CONSOLE_BYTES = 32 * 1024;
const MAX_HANDOFF_BYTES = 256 * 1024;
const textEncoder = new TextEncoder();

function utf8Tail(value: string, maxBytes: number): string {
  const bytes = textEncoder.encode(value);
  if (bytes.length <= maxBytes) {
    return value;
  }
  let start = bytes.length - maxBytes;
  while (start < bytes.length) {
    try {
      return new TextDecoder("utf-8", { fatal: true }).decode(
        bytes.subarray(start),
      );
    } catch {
      start++;
    }
  }
  return "";
}

function boundedConsoleTail(
  lines: HandoffPayload["consoleTail"],
): HandoffPayload["consoleTail"] {
  const tail: HandoffPayload["consoleTail"] = [];
  let remaining = MAX_CONSOLE_BYTES;
  for (const line of lines.slice(-MAX_CONSOLE_LINES).reverse()) {
    if (remaining === 0) {
      break;
    }
    const data = utf8Tail(line.data, remaining);
    if (data) {
      tail.unshift({ ...line, data });
      remaining -= textEncoder.encode(data).length;
    }
  }
  return tail;
}

function plainText(html: string): string {
  const element = document.createElement("div");
  element.innerHTML = sanitizeHtml(html);
  return element.textContent ?? "";
}

export function SendErrorReportButton({
  cellId,
  error,
  traceback,
  tracebackMatch,
  preferLastRunCode = false,
  fallbackToConsoleTraceback = false,
}: {
  cellId: CellId | undefined;
  error: string;
  traceback: string;
  tracebackMatch?: string;
  preferLastRunCode?: boolean;
  fallbackToConsoleTraceback?: boolean;
}) {
  const store = useStore();
  const pairPreview = useAtomValue(pairPreviewAtom);
  const presence = useAtomValue(participantPresenceAtom);
  const [sending, setSending] = useState(false);
  const pending = useRef(false);

  if (!pairPreview || !presence?.attached || !cellId) {
    return null;
  }

  const send = async () => {
    if (pending.current) {
      return;
    }
    pending.current = true;
    setSending(true);
    try {
      const { cellData, cellRuntime } = store.get(notebookAtom);
      const cell = cellData[cellId];
      const runtime = cellRuntime[cellId];
      if (!cell || !runtime) {
        throw new Error("Cell no longer exists.");
      }

      const consoleLines = runtime.consoleOutputs
        .flatMap((output) => {
          const { channel, data } = output;
          if (
            (channel !== "stdout" && channel !== "stderr") ||
            typeof data !== "string" ||
            output.mimetype === "application/vnd.marimo+traceback"
          ) {
            return [];
          }
          const text = output.mimetype === "text/html" ? plainText(data) : data;
          return text
            .split(/\r?\n/)
            .filter(Boolean)
            .map((line) => ({ channel, data: line }));
        })
        .slice(-MAX_CONSOLE_LINES);
      const consoleTail = boundedConsoleTail(consoleLines);
      let tracebackText = plainText(traceback);
      if (fallbackToConsoleTraceback && !tracebackText.trim()) {
        const consoleTraceback = runtime.consoleOutputs.findLast(
          (output) =>
            output.mimetype === "application/vnd.marimo+traceback" &&
            typeof output.data === "string",
        );
        if (consoleTraceback && typeof consoleTraceback.data === "string") {
          const candidate = plainText(consoleTraceback.data);
          // A previous run can leave a traceback in the console.
          if (candidate.includes(tracebackMatch ?? error)) {
            tracebackText = candidate;
          }
        }
      }
      const payload: HandoffPayload = {
        cellId,
        error,
        code: preferLastRunCode ? (cell.lastCodeRun ?? cell.code) : cell.code,
        traceback: tracebackText,
        consoleTail,
      };
      if (textEncoder.encode(JSON.stringify(payload)).length > MAX_HANDOFF_BYTES) {
        toast({ variant: "danger", title: "Error report is too large to send" });
        return;
      }
      await API.post<HandoffPayload, { seq: number }>(
        "/participants/handoff",
        payload,
      );
      toast({ title: `Sent to ${presence.harness.displayName}` });
    } catch {
      toast({ variant: "danger", title: "Could not send error report" });
    } finally {
      pending.current = false;
      setSending(false);
    }
  };

  return (
    <Button size="xs" variant="outline" disabled={sending} onClick={send}>
      <SendIcon className="h-3 w-3 mr-2" />
      Send error to agent
    </Button>
  );
}
