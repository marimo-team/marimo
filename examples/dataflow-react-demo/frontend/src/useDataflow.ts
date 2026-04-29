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

      if (!resp.ok) {
        setState((s) => ({
          ...s,
          loading: false,
          error: `Run failed: ${resp.status}`,
        }));
        return;
      }

      // Extract session ID from header
      const sid = resp.headers.get("x-dataflow-session-id");
      if (sid) sessionIdRef.current = sid;

      // Parse SSE from response body
      const text = await resp.text();
      const events = parseSSE(text);

      const vars: Record<string, VarUpdate> = {};
      let runId: string | null = null;
      let elapsed: number | null = null;

      for (const event of events) {
        if (event.type === "var") {
          const d = event.data;
          vars[d.name as string] = {
            name: d.name as string,
            kind: d.kind as string,
            value: d.value,
            encoding: d.encoding as string,
            runId: d.run_id as string,
          };
        } else if (event.type === "var-error") {
          vars[event.data.name as string] = {
            name: event.data.name as string,
            kind: "error",
            value: event.data.error,
            encoding: "json",
            runId: event.data.run_id as string,
          };
        } else if (event.type === "run") {
          runId = event.data.run_id as string;
          if (event.data.status === "done") {
            elapsed = (event.data.elapsed_ms as number) ?? null;
          }
        }
      }

      setState((s) => ({
        ...s,
        variables: { ...s.variables, ...vars },
        loading: false,
        runId,
        elapsed,
      }));
    },
    [],
  );

  return { ...state, fetchSchema, run };
}

interface ParsedEvent {
  type: string;
  data: Record<string, unknown>;
}

function parseSSE(text: string): ParsedEvent[] {
  const events: ParsedEvent[] = [];
  const blocks = text.split("\n\n");
  for (const block of blocks) {
    const lines = block.split("\n");
    let eventType = "";
    let data = "";
    for (const line of lines) {
      if (line.startsWith("event: ")) {
        eventType = line.slice(7);
      } else if (line.startsWith("data: ")) {
        data = line.slice(6);
      }
    }
    if (eventType && data) {
      try {
        events.push({ type: eventType, data: JSON.parse(data) });
      } catch {
        // skip malformed
      }
    }
  }
  return events;
}
