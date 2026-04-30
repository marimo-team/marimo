import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useSyncExternalStore,
} from "react";

// ---------------------------------------------------------------------------
// Types — mirror marimo._dataflow.protocol
// ---------------------------------------------------------------------------

export type Kind =
  | "null"
  | "boolean"
  | "integer"
  | "number"
  | "string"
  | "bytes"
  | "list"
  | "dict"
  | "tuple"
  | "table"
  | "ui_element"
  | "any"
  | (string & {});

export interface InputSchema {
  name: string;
  kind: Kind;
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

export interface OutputSchema {
  name: string;
  kind: Kind;
  description?: string | null;
}

export interface DataflowSchema {
  inputs: InputSchema[];
  outputs: OutputSchema[];
  schemaId: string;
}

export interface VarUpdate<T = unknown> {
  name: string;
  kind: Kind;
  value: T;
  encoding: string;
  runId: string;
  // Local timestamp at receipt; useful for animations / debugging.
  ts: number;
}

export interface RunStatus {
  loading: boolean;
  error: string | null;
  runId: string | null;
  /**
   * Wall-clock from request queue to the kernel's
   * ``CompletedRunNotification`` — i.e. the time for the *full* run the
   * kernel decided to execute. With an editor attached this includes
   * cells outside the subscription closure and is not what most apps
   * want to display.
   */
  elapsedMs: number | null;
  /** Time from request start to the first ``var`` event arrival. */
  firstVarMs: number | null;
  /**
   * Time from request start to the moment every subscribed variable
   * has arrived. This is "when the UI was ready" and is usually the
   * number app developers want.
   */
  subscriptionsResolvedMs: number | null;
  schemaId: string | null;
}

// ---------------------------------------------------------------------------
// Client — framework-agnostic store with per-variable subscriptions
// ---------------------------------------------------------------------------

export interface DataflowClientOptions {
  baseUrl: string;
  /** Auto-trigger a run when inputs change or a new variable is subscribed. */
  autoRun?: boolean;
  /** Coalesce rapid input changes (slider drags) into a single run. */
  debounceMs?: number;
}

export class DataflowClient {
  private readonly baseUrl: string;
  private autoRun: boolean;
  private readonly debounceMs: number;

  private schema: DataflowSchema | null = null;
  private values = new Map<string, VarUpdate>();
  private inputs = new Map<string, unknown>();
  private status: RunStatus = {
    loading: false,
    error: null,
    runId: null,
    elapsedMs: null,
    firstVarMs: null,
    subscriptionsResolvedMs: null,
    schemaId: null,
  };
  // Per-run timing bookkeeping. ``runStartedAt`` is captured client-side
  // right before the fetch so the elapsed numbers include network RTT,
  // which is what the user actually waits on.
  private runStartedAt: number | null = null;
  private pendingSubscribed = new Set<string>();
  // Refcount of components currently observing each variable. Used as the
  // ``subscribe`` set on /run so the kernel only computes what the UI cares
  // about; mounting/unmounting components dynamically reshapes the graph.
  private subRefcount = new Map<string, number>();

  private varListeners = new Map<string, Set<() => void>>();
  private inputListeners = new Map<string, Set<() => void>>();
  private schemaListeners = new Set<() => void>();
  private statusListeners = new Set<() => void>();
  // Catch-all listeners for the debug surface; fired any time *any*
  // variable updates or the subscribed set changes.
  private valuesListeners = new Set<() => void>();
  private subscriptionsListeners = new Set<() => void>();
  // Snapshots cached as stable references for ``useSyncExternalStore``.
  // They're rebuilt only when their version counter advances.
  private subscriptionsSnapshot: string[] = [];
  private valuesSnapshot: Record<string, VarUpdate> = {};
  private valuesVersion = 0;
  private valuesSnapshotVersion = 0;

  private debounceTimer: ReturnType<typeof setTimeout> | null = null;
  private inflight: AbortController | null = null;
  private schemaInflight: Promise<DataflowSchema | null> | null = null;
  private schemaFetched = false;

  constructor(opts: DataflowClientOptions) {
    this.baseUrl = opts.baseUrl;
    this.autoRun = opts.autoRun ?? true;
    this.debounceMs = opts.debounceMs ?? 50;
  }

  /** Enable or disable autorun on input changes. Run buttons always fire. */
  setAutoRun(value: boolean): void {
    this.autoRun = value;
  }

  // ---------- schema ----------

  getSchema(): DataflowSchema | null {
    return this.schema;
  }

  subscribeSchema(cb: () => void): () => void {
    this.schemaListeners.add(cb);
    if (!this.schemaFetched) {
      this.schemaFetched = true;
      void this.refreshSchema();
    }
    return () => this.schemaListeners.delete(cb);
  }

  async refreshSchema(): Promise<DataflowSchema | null> {
    if (this.schemaInflight) return this.schemaInflight;
    this.schemaInflight = this.doRefreshSchema();
    try {
      return await this.schemaInflight;
    } finally {
      this.schemaInflight = null;
    }
  }

  private async doRefreshSchema(): Promise<DataflowSchema | null> {
    try {
      const resp = await fetch(`${this.baseUrl}/schema`);
      if (!resp.ok) {
        this.setStatus({ error: `schema fetch failed: ${resp.status}` });
        return null;
      }
      const next = (await resp.json()) as DataflowSchema;
      const prevId = this.schema?.schemaId ?? null;
      this.schema = next;
      // Seed inputs from defaults for fields the user hasn't touched.
      for (const inp of next.inputs) {
        if (!this.inputs.has(inp.name) && inp.default !== undefined) {
          this.inputs.set(inp.name, inp.default);
          this.notifyInput(inp.name);
        }
      }
      if (prevId !== next.schemaId) {
        this.setStatus({ schemaId: next.schemaId });
      }
      this.notifyAll(this.schemaListeners);
      if (this.autoRun && this.subRefcount.size > 0) this.scheduleRun();
      return next;
    } catch (e) {
      this.setStatus({ error: e instanceof Error ? e.message : String(e) });
      return null;
    }
  }

  // ---------- variables ----------

  getValue(name: string): VarUpdate | undefined {
    return this.values.get(name);
  }

  subscribeVar(name: string, cb: () => void): () => void {
    let listeners = this.varListeners.get(name);
    if (!listeners) {
      listeners = new Set();
      this.varListeners.set(name, listeners);
    }
    listeners.add(cb);
    return () => {
      listeners.delete(cb);
      if (listeners.size === 0) this.varListeners.delete(name);
    };
  }

  /**
   * Increment refcount for a variable. The first subscriber adds it to the
   * server-side ``subscribe`` set on the next run. The returned function
   * decrements the refcount on unmount.
   */
  retain(name: string): () => void {
    const next = (this.subRefcount.get(name) ?? 0) + 1;
    this.subRefcount.set(name, next);
    if (next === 1) {
      this.bumpSubscriptions();
      if (this.autoRun && this.schema) this.scheduleRun();
    }
    let released = false;
    return () => {
      if (released) return;
      released = true;
      const cur = (this.subRefcount.get(name) ?? 1) - 1;
      if (cur <= 0) {
        this.subRefcount.delete(name);
        this.bumpSubscriptions();
      } else {
        this.subRefcount.set(name, cur);
      }
    };
  }

  /** Names with at least one mounted observer, sorted for stable rendering. */
  getSubscriptions(): string[] {
    return this.subscriptionsSnapshot;
  }

  subscribeSubscriptions(cb: () => void): () => void {
    this.subscriptionsListeners.add(cb);
    return () => this.subscriptionsListeners.delete(cb);
  }

  /** Snapshot of every variable received this session (for debug views). */
  getValuesSnapshot(): Record<string, VarUpdate> {
    if (this.valuesSnapshotVersion !== this.valuesVersion) {
      this.valuesSnapshot = Object.fromEntries(this.values);
      this.valuesSnapshotVersion = this.valuesVersion;
    }
    return this.valuesSnapshot;
  }

  subscribeValuesSnapshot(cb: () => void): () => void {
    this.valuesListeners.add(cb);
    return () => this.valuesListeners.delete(cb);
  }

  // ---------- inputs ----------

  getInput(name: string): unknown {
    return this.inputs.get(name);
  }

  subscribeInput(name: string, cb: () => void): () => void {
    let listeners = this.inputListeners.get(name);
    if (!listeners) {
      listeners = new Set();
      this.inputListeners.set(name, listeners);
    }
    listeners.add(cb);
    return () => {
      listeners.delete(cb);
      if (listeners.size === 0) this.inputListeners.delete(name);
    };
  }

  setInput(name: string, value: unknown): void {
    const runButton = this.isRunButton(name);
    // Run buttons are fire-once: every ``setInput`` should produce a run,
    // even if the local cache already says ``true``. For every other input
    // skip the round-trip when the value didn't actually change.
    if (!runButton && Object.is(this.inputs.get(name), value)) return;

    this.inputs.set(name, value);
    this.notifyInput(name);

    if (runButton) {
      // Fire immediately (no debounce). The first synchronous chunk of
      // ``runNow`` snapshots ``this.inputs`` into the request body before
      // yielding on ``await fetch(...)``, so resetting the local cache to
      // ``false`` *after* ``run()`` returns is safe — the in-flight request
      // still carries ``true``. This mirrors ``mo.ui.run_button``'s
      // server-side auto-reset on the client so subsequent autoruns don't
      // keep resending ``true`` and refiring the side effect.
      this.run();
      this.inputs.set(name, false);
      this.notifyInput(name);
      return;
    }

    if (this.autoRun) this.scheduleRun();
  }

  private isRunButton(name: string): boolean {
    if (!this.schema) return false;
    const input = this.schema.inputs.find((i) => i.name === name);
    return input?.constraints?.ui === "run_button";
  }

  // ---------- status ----------

  getStatus(): RunStatus {
    return this.status;
  }

  subscribeStatus(cb: () => void): () => void {
    this.statusListeners.add(cb);
    return () => this.statusListeners.delete(cb);
  }

  // ---------- run ----------

  /** Manually trigger a run; bypasses debounce. */
  run(): void {
    if (this.debounceTimer) {
      clearTimeout(this.debounceTimer);
      this.debounceTimer = null;
    }
    void this.runNow();
  }

  /** Cancel any in-flight run + pending debounced run. */
  dispose(): void {
    if (this.debounceTimer) {
      clearTimeout(this.debounceTimer);
      this.debounceTimer = null;
    }
    if (this.inflight) {
      this.inflight.abort();
      this.inflight = null;
    }
  }

  private scheduleRun(): void {
    if (this.debounceTimer) clearTimeout(this.debounceTimer);
    this.debounceTimer = setTimeout(() => {
      this.debounceTimer = null;
      void this.runNow();
    }, this.debounceMs);
  }

  private async runNow(): Promise<void> {
    if (!this.schema) return;
    if (this.subRefcount.size === 0) return;

    if (this.inflight) this.inflight.abort();
    const abort = new AbortController();
    this.inflight = abort;

    const validOutputs = new Set(this.schema.outputs.map((o) => o.name));
    const subscribed = Array.from(this.subRefcount.keys()).filter((n) =>
      validOutputs.has(n),
    );
    const inputs: Record<string, unknown> = {};
    for (const [k, v] of this.inputs) inputs[k] = v;

    this.runStartedAt = performance.now();
    this.pendingSubscribed = new Set(subscribed);
    this.setStatus({
      loading: true,
      error: null,
      elapsedMs: null,
      firstVarMs: null,
      subscriptionsResolvedMs: null,
    });

    try {
      const resp = await fetch(`${this.baseUrl}/run`, {
        method: "POST",
        headers: {
          "content-type": "application/json",
          accept: "text/event-stream",
        },
        body: JSON.stringify({ inputs, subscribe: subscribed }),
        signal: abort.signal,
      });
      if (!resp.ok || !resp.body) {
        throw new Error(`run failed: ${resp.status}`);
      }

      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buf = "";
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        let idx;
        while ((idx = buf.indexOf("\n\n")) !== -1) {
          this.handleSseBlock(buf.slice(0, idx));
          buf = buf.slice(idx + 2);
        }
      }
      const tail = buf.trim();
      if (tail) this.handleSseBlock(tail);
    } catch (e) {
      if (abort.signal.aborted) return;
      this.setStatus({
        loading: false,
        error: e instanceof Error ? e.message : String(e),
      });
    } finally {
      if (this.inflight === abort) this.inflight = null;
    }
  }

  private handleSseBlock(block: string): void {
    let event = "";
    let data = "";
    for (const line of block.split("\n")) {
      if (line.startsWith("event:")) event = line.slice(6).trim();
      else if (line.startsWith("data:")) data += line.slice(5).trim();
    }
    if (!data) return;
    let parsed: Record<string, unknown>;
    try {
      parsed = JSON.parse(data);
    } catch {
      return;
    }
    this.dispatch(event, parsed);
  }

  private dispatch(event: string, data: Record<string, unknown>): void {
    if (event === "var") {
      const update: VarUpdate = {
        name: data.name as string,
        kind: data.kind as Kind,
        value: data.value,
        encoding: data.encoding as string,
        runId: data.run_id as string,
        ts: Date.now(),
      };
      this.values.set(update.name, update);
      this.notifyVar(update.name);
      this.noteVarArrival(update.name);
    } else if (event === "var-error") {
      // Per-variable failures (e.g. a subscribed var whose cell ``mo.stop``'d
      // or raised) clear the variable's value but do *not* trip the run-level
      // ``status.error``. Consumers reading the variable see ``undefined``;
      // unrelated subscribers keep their values.
      const name = data.name as string;
      const update: VarUpdate = {
        name,
        kind: "any",
        value: undefined,
        encoding: "json",
        runId: data.run_id as string,
        ts: Date.now(),
      };
      this.values.set(name, update);
      this.notifyVar(name);
      this.noteVarArrival(name);
    } else if (event === "schema") {
      // Fold in any inline schema updates (currently /schema is the canonical
      // source; we still fire schema listeners so live edits in the editor
      // can reach the React app without a manual refresh).
      const schema = data.schema as DataflowSchema | undefined;
      if (schema) {
        this.schema = schema;
        this.setStatus({ schemaId: schema.schemaId });
        this.notifyAll(this.schemaListeners);
      }
    } else if (event === "run") {
      const status = data.status as string;
      if (status === "started") {
        this.setStatus({ runId: data.run_id as string, loading: true });
      } else if (status === "done") {
        this.setStatus({
          runId: data.run_id as string,
          loading: false,
          elapsedMs: (data.elapsed_ms as number) ?? null,
        });
      } else if (status === "error") {
        this.setStatus({
          loading: false,
          error: (data.message as string) ?? "run failed",
        });
      }
    }
  }

  /**
   * Update timing fields when a subscribed variable lands. ``firstVarMs``
   * is the TTFV (time-to-first-var); ``subscriptionsResolvedMs`` fires
   * once every variable in the request's ``subscribe`` set has reported.
   */
  private noteVarArrival(name: string): void {
    if (this.runStartedAt === null) return;
    const dt = performance.now() - this.runStartedAt;
    const patch: Partial<RunStatus> = {};
    if (this.status.firstVarMs === null) patch.firstVarMs = dt;
    if (
      this.pendingSubscribed.delete(name) &&
      this.pendingSubscribed.size === 0
    ) {
      patch.subscriptionsResolvedMs = dt;
    }
    if (Object.keys(patch).length > 0) this.setStatus(patch);
  }

  // ---------- notify helpers ----------

  private setStatus(patch: Partial<RunStatus>): void {
    this.status = { ...this.status, ...patch };
    this.notifyAll(this.statusListeners);
  }

  private notifyVar(name: string): void {
    const ls = this.varListeners.get(name);
    if (ls) for (const cb of ls) cb();
    this.valuesVersion++;
    this.notifyAll(this.valuesListeners);
  }

  private notifyInput(name: string): void {
    const ls = this.inputListeners.get(name);
    if (ls) for (const cb of ls) cb();
  }

  private bumpSubscriptions(): void {
    this.subscriptionsSnapshot = Array.from(this.subRefcount.keys()).sort();
    this.notifyAll(this.subscriptionsListeners);
  }

  private notifyAll(listeners: Set<() => void>): void {
    for (const cb of listeners) cb();
  }
}

// ---------------------------------------------------------------------------
// React glue
// ---------------------------------------------------------------------------

const DataflowContext = createContext<DataflowClient | null>(null);

export interface DataflowProviderProps extends DataflowClientOptions {
  children: ReactNode;
}

export function DataflowProvider({ children, ...opts }: DataflowProviderProps) {
  const clientRef = useRef<DataflowClient | null>(null);
  if (!clientRef.current) clientRef.current = new DataflowClient(opts);

  // Forward live prop changes to the existing client instance instead of
  // rebuilding it; rebuilding would drop subscriptions and invalidate any
  // values already on screen.
  const { autoRun } = opts;
  useEffect(() => {
    if (autoRun !== undefined) clientRef.current!.setAutoRun(autoRun);
  }, [autoRun]);

  useEffect(() => {
    const client = clientRef.current!;
    void client.refreshSchema();
    return () => client.dispose();
  }, []);

  return (
    <DataflowContext.Provider value={clientRef.current}>
      {children}
    </DataflowContext.Provider>
  );
}

function useClient(): DataflowClient {
  const c = useContext(DataflowContext);
  if (!c) {
    throw new Error(
      "useDataflow* hooks must be used inside a <DataflowProvider>",
    );
  }
  return c;
}

/** Returns the current schema, re-rendering only when it changes. */
export function useDataflowSchema(): DataflowSchema | null {
  const client = useClient();
  return useSyncExternalStore(
    useCallback((cb) => client.subscribeSchema(cb), [client]),
    () => client.getSchema(),
    () => client.getSchema(),
  );
}

/**
 * Subscribe to a single variable. The component re-renders only when *this*
 * variable's value changes; sibling variables don't trigger a re-render.
 *
 * Mounting this hook adds the variable to the server-side subscription set;
 * unmounting removes it. This is what lets the kernel prune cells whose
 * outputs nobody is currently rendering.
 */
export function useDataflowValue<T = unknown>(name: string): T | undefined {
  const update = useDataflowVariable<T>(name);
  return update?.value;
}

/** Lower-level variant returning the full ``VarUpdate`` (run id, kind, ts). */
export function useDataflowVariable<T = unknown>(
  name: string,
): VarUpdate<T> | undefined {
  const client = useClient();
  useEffect(() => client.retain(name), [client, name]);
  return useSyncExternalStore(
    useCallback((cb) => client.subscribeVar(name, cb), [client, name]),
    () => client.getValue(name) as VarUpdate<T> | undefined,
    () => client.getValue(name) as VarUpdate<T> | undefined,
  );
}

/**
 * Two-way bind to a named input, like ``useState``. Defaults flow from the
 * schema; ``fallback`` is used until the schema arrives.
 */
export function useDataflowInput<T = unknown>(
  name: string,
  fallback?: T,
): [T | undefined, (value: T) => void] {
  const client = useClient();
  const value = useSyncExternalStore(
    useCallback((cb) => client.subscribeInput(name, cb), [client, name]),
    () => client.getInput(name),
    () => client.getInput(name),
  );
  const set = useCallback(
    (v: T) => client.setInput(name, v),
    [client, name],
  );
  const schema = useDataflowSchema();
  const effective = useMemo(() => {
    if (value !== undefined) return value as T;
    const inp = schema?.inputs.find((i) => i.name === name);
    if (inp && inp.default !== undefined) return inp.default as T;
    return fallback;
  }, [value, schema, name, fallback]);
  return [effective, set];
}

/** Returns the latest run status (loading, errors, elapsed time). */
export function useDataflowStatus(): RunStatus {
  const client = useClient();
  return useSyncExternalStore(
    useCallback((cb) => client.subscribeStatus(cb), [client]),
    () => client.getStatus(),
    () => client.getStatus(),
  );
}

/** Imperative trigger for a run (bypasses debounce). */
export function useDataflowRun(): () => void {
  const client = useClient();
  return useCallback(() => client.run(), [client]);
}

/**
 * Names currently subscribed to (refcount > 0). Useful for debug views;
 * mirrors the ``subscribe`` set the client sends on each ``/run``.
 */
export function useDataflowSubscriptions(): string[] {
  const client = useClient();
  return useSyncExternalStore(
    useCallback((cb) => client.subscribeSubscriptions(cb), [client]),
    () => client.getSubscriptions(),
    () => client.getSubscriptions(),
  );
}

/**
 * Snapshot of every variable received in this session, keyed by name.
 * Re-renders on *any* variable update, so prefer ``useDataflowValue`` in
 * production components and reserve this for debug surfaces.
 */
export function useDataflowValuesSnapshot(): Record<string, VarUpdate> {
  const client = useClient();
  return useSyncExternalStore(
    useCallback((cb) => client.subscribeValuesSnapshot(cb), [client]),
    () => client.getValuesSnapshot(),
    () => client.getValuesSnapshot(),
  );
}

/** Escape hatch for advanced use: get the underlying client. */
export function useDataflowClient(): DataflowClient {
  return useClient();
}
