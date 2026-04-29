import { useCallback, useRef, useState } from "react";

export interface InputSchema {
  name: string;
  kind: string;
  default?: unknown;
  description?: string | null;
  required?: boolean;
  constraints?: {
    min?: number;
    max?: number;
    step?: number;
    options?: unknown[];
    ui?: string;
  } | null;
}

export interface DataflowSchema {
  inputs: InputSchema[];
  outputs: Array<{ name: string; kind: string }>;
  triggers: Array<{ name: string }>;
  schemaId: string;
}

export interface VarUpdate {
  name: string;
  kind: string;
  value: unknown;
  encoding: string;
  runId: string;
}

interface DataflowState {
  schema: DataflowSchema | null;
  variables: Record<string, VarUpdate>;
  loading: boolean;
  error: string | null;
  runId: string | null;
  elapsed: number | null;
}

const API_BASE = "/api/v1/dataflow";

export function useDataflow() {
  const [state, setState] = useState<DataflowState>({
    schema: null,
    variables: {},
    loading: false,
    error: null,
    runId: null,
    elapsed: null,
  });
  const sessionIdRef = useRef<string | null>(null);

  const fetchSchema = useCallback(async () => {
    const resp = await fetch(`${API_BASE}/schema`);
    if (!resp.ok) {
      setState((s) => ({ ...s, error: `Schema fetch failed: ${resp.status}` }));
      return;
    }
    const schema: DataflowSchema = await resp.json();
    setState((s) => ({ ...s, schema }));
  }, []);

  const run = useCallback(
    async (inputs: Record<string, unknown>, subscribe: string[]) => {
      setState((s) => ({ ...s, loading: true, error: null }));

      const body = {
        inputs,
        subscribe,
        sessionId: sessionIdRef.current,
      };

      const resp = await fetch(`${API_BASE}/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });

      if (!resp.ok || !resp.body) {
        setState((s) => ({
          ...s,
          loading: false,
          error: `Run failed: ${resp.status}`,
        }));
        return;
      }

      const sid = resp.headers.get("x-dataflow-session-id");
      if (sid) sessionIdRef.current = sid;

      // Stream SSE events as they arrive so subscribed variables that finish
      // first (e.g. `stats` while a slow cell is still running) land in the
      // UI immediately instead of after the whole run.
      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      const applyEvent = (event: ParsedEvent) => {
        if (event.type === "var") {
          const d = event.data;
          const update: VarUpdate = {
            name: d.name as string,
            kind: d.kind as string,
            value: d.value,
            encoding: d.encoding as string,
            runId: d.run_id as string,
          };
          setState((s) => ({
            ...s,
            variables: { ...s.variables, [update.name]: update },
          }));
        } else if (event.type === "var-error") {
          const update: VarUpdate = {
            name: event.data.name as string,
            kind: "error",
            value: event.data.error,
            encoding: "json",
            runId: event.data.run_id as string,
          };
          setState((s) => ({
            ...s,
            variables: { ...s.variables, [update.name]: update },
          }));
        } else if (event.type === "run") {
          if (event.data.status === "done") {
            setState((s) => ({
              ...s,
              loading: false,
              runId: event.data.run_id as string,
              elapsed: (event.data.elapsed_ms as number) ?? null,
            }));
          } else {
            setState((s) => ({
              ...s,
              runId: event.data.run_id as string,
            }));
          }
        }
      };

      // SSE messages are separated by a blank line. Buffer until we see one,
      // parse the completed block, and keep any trailing partial chunk for
      // the next read.
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        let idx;
        while ((idx = buffer.indexOf("\n\n")) !== -1) {
          const block = buffer.slice(0, idx);
          buffer = buffer.slice(idx + 2);
          const event = parseSSEBlock(block);
          if (event) applyEvent(event);
        }
      }
      const tail = buffer.trim();
      if (tail) {
        const event = parseSSEBlock(tail);
        if (event) applyEvent(event);
      }
    },
    [],
  );

  return { ...state, fetchSchema, run };
}

interface ParsedEvent {
  type: string;
  data: Record<string, unknown>;
}

function parseSSEBlock(block: string): ParsedEvent | null {
  let eventType = "";
  let data = "";
  for (const line of block.split("\n")) {
    if (line.startsWith("event: ")) {
      eventType = line.slice(7);
    } else if (line.startsWith("data: ")) {
      data = line.slice(6);
    }
  }
  if (!eventType || !data) return null;
  try {
    return { type: eventType, data: JSON.parse(data) };
  } catch {
    return null;
  }
}
