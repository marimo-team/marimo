import { useMemo, useState } from "react";
import {
  DataflowProvider,
  type InputSchema,
  useDataflowInput,
  useDataflowSchema,
  useDataflowStatus,
  useDataflowSubscriptions,
  useDataflowValue,
  useDataflowValuesSnapshot,
  type VarUpdate,
} from "./dataflow";

export function App() {
  return (
    <DataflowProvider baseUrl="/api/v1/dataflow">
      <Page />
    </DataflowProvider>
  );
}

function Page() {
  // Conditional mount — flipping this off un-mounts ``<SlowThreshold />``,
  // which releases its retain on ``slow_threshold`` and the next /run is
  // pruned to skip the 0.5s sleep cell entirely.
  const [showSlow, setShowSlow] = useState(true);

  return (
    <div style={styles.container}>
      <header style={styles.header}>
        <h1 style={styles.title}>marimo Dataflow API Demo</h1>
        <p style={styles.subtitle}>
          Schema-driven inputs · per-variable subscriptions · streaming outputs
        </p>
      </header>

      <div style={styles.grid}>
        <Inputs showSlow={showSlow} onToggleSlow={setShowSlow} />
        <Stats />
        {showSlow && <SlowThreshold />}
        <Histogram />
        <Table />
      </div>

      <DebugFooter />
      <SchemaFooter />
    </div>
  );
}

// ---------- Inputs ----------

function Inputs({
  showSlow,
  onToggleSlow,
}: {
  showSlow: boolean;
  onToggleSlow: (v: boolean) => void;
}) {
  const schema = useDataflowSchema();
  const status = useDataflowStatus();

  return (
    <section style={styles.card}>
      <h2 style={styles.cardTitle}>Inputs</h2>
      {schema?.inputs.map((input) => (
        <DynamicInput key={input.name} input={input} />
      ))}
      <div style={styles.inputGroup}>
        <label style={styles.checkbox}>
          <input
            type="checkbox"
            checked={showSlow}
            onChange={(e) => onToggleSlow(e.target.checked)}
          />
          Subscribe to <code>slow_threshold</code>
        </label>
      </div>
      {status.elapsedMs !== null && (
        <p style={styles.meta}>
          Computed in {status.elapsedMs.toFixed(0)}ms
          {status.loading && " (running...)"}
        </p>
      )}
      {status.error && <p style={styles.error}>{status.error}</p>}
    </section>
  );
}

function DynamicInput({ input }: { input: InputSchema }) {
  const [value, setValue] = useDataflowInput<unknown>(
    input.name,
    input.default,
  );
  const ui = input.constraints?.ui;

  const node = useMemo(() => {
    if (ui === "slider") {
      return (
        <input
          type="range"
          min={input.constraints?.min as number | undefined}
          max={input.constraints?.max as number | undefined}
          step={(input.constraints?.step as number | undefined) ?? 1}
          value={Number(value ?? 0)}
          onChange={(e) => setValue(Number(e.target.value))}
          style={styles.slider}
        />
      );
    }
    if (ui === "dropdown") {
      const options = (input.constraints?.options as unknown[]) ?? [];
      return (
        <select
          value={String(value ?? "")}
          onChange={(e) => setValue(e.target.value)}
          style={styles.select}
        >
          {options.map((opt) => (
            <option key={String(opt)} value={String(opt)}>
              {String(opt)}
            </option>
          ))}
        </select>
      );
    }
    if (ui === "switch") {
      return (
        <input
          type="checkbox"
          checked={Boolean(value)}
          onChange={(e) => setValue(e.target.checked)}
        />
      );
    }
    return (
      <input
        type="text"
        value={String(value ?? "")}
        onChange={(e) => setValue(e.target.value)}
        style={styles.select}
      />
    );
  }, [ui, value, input.constraints, setValue]);

  return (
    <div style={styles.inputGroup}>
      <label style={styles.label}>
        {input.description ?? input.name}
        {ui === "slider" && (
          <strong style={{ marginLeft: 6 }}>{String(value)}</strong>
        )}
      </label>
      {node}
    </div>
  );
}

// ---------- Outputs ----------
//
// Each output is a focused component that subscribes to *one* variable.
// Mounting the component adds it to the server's subscription set, so the
// kernel only computes what's actually rendered. Re-renders are scoped to
// just the variable each component reads.

function Stats() {
  const stats = useDataflowValue<Record<string, number>>("stats");
  if (!stats) return null;
  return (
    <section style={styles.card}>
      <h2 style={styles.cardTitle}>Statistics</h2>
      <div style={styles.statsGrid}>
        {Object.entries(stats).map(([key, val]) => (
          <div key={key} style={styles.statItem}>
            <div style={styles.statValue}>{val}</div>
            <div style={styles.statLabel}>{key}</div>
          </div>
        ))}
      </div>
    </section>
  );
}

function SlowThreshold() {
  // The notebook sleeps 0.5s before producing this; with per-cell streaming
  // the panels above land first and this number trickles in once its cell
  // finishes — visible proof that the SSE stream is incremental, not batched.
  const value = useDataflowValue<number>("slow_threshold");
  return (
    <section style={styles.card}>
      <h2 style={styles.cardTitle}>Slow threshold (streamed)</h2>
      <p style={styles.meta}>
        This cell sleeps 0.5s. Other panels render first; this number
        arrives once the slow cell finishes.
      </p>
      <div style={styles.statValue}>
        {value === undefined ? "…" : value}
      </div>
    </section>
  );
}

function Histogram() {
  const histogram = useDataflowValue<Array<{ bucket: string; count: number }>>(
    "histogram",
  );
  if (!histogram || histogram.length === 0) return null;
  return (
    <section style={styles.card}>
      <h2 style={styles.cardTitle}>Value Distribution</h2>
      <div style={styles.histogram}>
        {histogram.map((h) => (
          <div key={h.bucket} style={styles.histBar}>
            <div
              style={{
                ...styles.histFill,
                height: `${Math.min(h.count * 20, 100)}%`,
              }}
            />
            <span style={styles.histLabel}>{h.bucket}</span>
            <span style={styles.histCount}>{h.count}</span>
          </div>
        ))}
      </div>
    </section>
  );
}

function Table() {
  const table = useDataflowValue<Array<Record<string, unknown>>>("table");
  if (!table || table.length === 0) return null;
  return (
    <section style={{ ...styles.card, gridColumn: "1 / -1" }}>
      <h2 style={styles.cardTitle}>Filtered Data ({table.length} rows)</h2>
      <div style={styles.tableWrap}>
        <table style={styles.table}>
          <thead>
            <tr>
              {Object.keys(table[0]).map((col) => (
                <th key={col} style={styles.th}>
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {table.map((row, i) => (
              <tr key={i}>
                {Object.values(row).map((val, j) => (
                  <td key={j} style={styles.td}>
                    {String(val)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function SchemaFooter() {
  const schema = useDataflowSchema();
  if (!schema) return null;
  return (
    <footer style={styles.footer}>
      <details>
        <summary style={styles.detailsSummary}>
          Schema (id: {schema.schemaId})
        </summary>
        <pre style={styles.pre}>{JSON.stringify(schema, null, 2)}</pre>
      </details>
    </footer>
  );
}

function DebugFooter() {
  // Reads the catch-all snapshot, so this re-renders on every var update.
  // That's deliberate for a debug view; production components should reach
  // for ``useDataflowValue(name)`` to scope their re-renders.
  const subscribed = useDataflowSubscriptions();
  const values = useDataflowValuesSnapshot();
  return (
    <footer style={styles.footer}>
      <details>
        <summary style={styles.detailsSummary}>
          Subscribed variables ({subscribed.length})
        </summary>
        {subscribed.length === 0 ? (
          <p style={styles.meta}>No mounted components subscribing.</p>
        ) : (
          <table style={styles.debugTable}>
            <thead>
              <tr>
                <th style={styles.th}>name</th>
                <th style={styles.th}>kind</th>
                <th style={styles.th}>run id</th>
                <th style={styles.th}>value</th>
              </tr>
            </thead>
            <tbody>
              {subscribed.map((name) => (
                <DebugRow key={name} name={name} update={values[name]} />
              ))}
            </tbody>
          </table>
        )}
      </details>
    </footer>
  );
}

function DebugRow({
  name,
  update,
}: {
  name: string;
  update: VarUpdate | undefined;
}) {
  return (
    <tr>
      <td style={styles.td}>
        <code>{name}</code>
      </td>
      <td style={styles.td}>{update?.kind ?? "—"}</td>
      <td style={styles.td}>
        <code>{update?.runId ?? "—"}</code>
      </td>
      <td style={styles.td}>
        <pre style={styles.preInline}>
          {update === undefined
            ? "(pending)"
            : truncate(JSON.stringify(update.value, null, 2), 400)}
        </pre>
      </td>
    </tr>
  );
}

function truncate(s: string, max: number): string {
  return s.length <= max ? s : `${s.slice(0, max)}…`;
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    maxWidth: 1200,
    margin: "0 auto",
    padding: "2rem",
    fontFamily:
      '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
    color: "#1a1a2e",
    background: "#f8f9fa",
    minHeight: "100vh",
  },
  header: { marginBottom: "2rem", textAlign: "center" },
  title: { fontSize: "2rem", margin: 0, color: "#16213e" },
  subtitle: { color: "#6c757d", marginTop: "0.5rem" },
  grid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))",
    gap: "1.5rem",
  },
  card: {
    background: "#fff",
    borderRadius: 12,
    padding: "1.5rem",
    boxShadow: "0 2px 8px rgba(0,0,0,0.06)",
    border: "1px solid #e9ecef",
  },
  cardTitle: {
    fontSize: "1.1rem",
    marginTop: 0,
    marginBottom: "1rem",
    color: "#495057",
  },
  inputGroup: { marginBottom: "1rem" },
  label: { display: "block", marginBottom: "0.4rem", fontWeight: 500 },
  checkbox: {
    display: "flex",
    alignItems: "center",
    gap: "0.4rem",
    fontSize: "0.9rem",
  },
  slider: { width: "100%" },
  select: {
    width: "100%",
    padding: "0.5rem",
    borderRadius: 6,
    border: "1px solid #dee2e6",
    fontSize: "0.9rem",
  },
  meta: { color: "#6c757d", fontSize: "0.85rem", marginTop: "1rem" },
  error: { color: "#dc3545", fontSize: "0.85rem", marginTop: "0.5rem" },
  statsGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(2, 1fr)",
    gap: "1rem",
  },
  statItem: { textAlign: "center" },
  statValue: { fontSize: "1.8rem", fontWeight: 700, color: "#0f3460" },
  statLabel: {
    fontSize: "0.8rem",
    color: "#6c757d",
    textTransform: "uppercase",
  },
  histogram: {
    display: "flex",
    alignItems: "flex-end",
    gap: "0.5rem",
    height: 120,
  },
  histBar: {
    flex: 1,
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    height: "100%",
    justifyContent: "flex-end",
  },
  histFill: {
    width: "100%",
    background: "linear-gradient(180deg, #4361ee, #3a0ca3)",
    borderRadius: "4px 4px 0 0",
    minHeight: 4,
    transition: "height 0.3s ease",
  },
  histLabel: { fontSize: "0.65rem", color: "#6c757d", marginTop: 4 },
  histCount: { fontSize: "0.75rem", fontWeight: 600 },
  tableWrap: { overflowX: "auto" },
  table: {
    width: "100%",
    borderCollapse: "collapse",
    fontSize: "0.85rem",
  },
  th: {
    textAlign: "left",
    padding: "0.5rem 0.75rem",
    borderBottom: "2px solid #dee2e6",
    fontWeight: 600,
    color: "#495057",
  },
  td: {
    padding: "0.4rem 0.75rem",
    borderBottom: "1px solid #f1f3f5",
  },
  footer: { marginTop: "2rem" },
  detailsSummary: { cursor: "pointer", color: "#6c757d", fontSize: "0.9rem" },
  pre: {
    background: "#f1f3f5",
    padding: "1rem",
    borderRadius: 8,
    fontSize: "0.8rem",
    overflow: "auto",
  },
  preInline: {
    background: "#f1f3f5",
    padding: "0.4rem 0.6rem",
    borderRadius: 4,
    fontSize: "0.75rem",
    margin: 0,
    maxWidth: 480,
    whiteSpace: "pre-wrap",
    overflowWrap: "anywhere",
  },
  debugTable: {
    width: "100%",
    borderCollapse: "collapse",
    fontSize: "0.85rem",
    marginTop: "0.75rem",
  },
};
