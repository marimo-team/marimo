import { useCallback, useEffect, useMemo, useState } from "react";
import { useDataflow, type InputSchema } from "./useDataflow";

export function App() {
  const { schema, variables, loading, error, elapsed, fetchSchema, run } =
    useDataflow();

  // Inputs are driven by the schema. The frontend doesn't hardcode anything
  // about which inputs exist or what their constraints are — it reads them
  // from `GET /schema` and renders accordingly.
  const [inputs, setInputs] = useState<Record<string, unknown>>({});
  const [subscribe, setSubscribe] = useState<string[]>([]);

  useEffect(() => {
    fetchSchema();
  }, [fetchSchema]);

  // Initialize input state from schema defaults and pick reasonable
  // default subscriptions on first schema load.
  useEffect(() => {
    if (!schema) return;
    setInputs((current) => {
      const next = { ...current };
      for (const input of schema.inputs) {
        if (next[input.name] === undefined) {
          next[input.name] = input.default;
        }
      }
      return next;
    });
    setSubscribe((current) =>
      current.length === 0
        ? schema.outputs.slice(0, 3).map((o) => o.name)
        : current,
    );
  }, [schema]);

  const handleRun = useCallback(() => {
    run(inputs, subscribe);
  }, [run, inputs, subscribe]);

  useEffect(() => {
    if (schema && Object.keys(inputs).length > 0) {
      handleRun();
    }
  }, [inputs, subscribe, schema]); // eslint-disable-line react-hooks/exhaustive-deps

  const stats = variables.stats?.value as Record<string, number> | undefined;
  const table = variables.table?.value as
    | Array<Record<string, unknown>>
    | undefined;
  const histogram = variables.histogram?.value as
    | Array<{ bucket: string; count: number }>
    | undefined;

  const setInput = (name: string, value: unknown) =>
    setInputs((prev) => ({ ...prev, [name]: value }));

  return (
    <div style={styles.container}>
      <header style={styles.header}>
        <h1 style={styles.title}>marimo Dataflow API Demo</h1>
        <p style={styles.subtitle}>
          Schema-driven inputs · streaming outputs · variable subscriptions
        </p>
      </header>

      <div style={styles.grid}>
        <section style={styles.card}>
          <h2 style={styles.cardTitle}>Inputs</h2>
          {schema?.inputs.map((input) => (
            <DynamicInput
              key={input.name}
              input={input}
              value={inputs[input.name]}
              onChange={(v) => setInput(input.name, v)}
            />
          ))}
          <div style={styles.inputGroup}>
            <label style={styles.label}>Subscriptions</label>
            {schema?.outputs.map((o) => (
              <label key={o.name} style={styles.checkbox}>
                <input
                  type="checkbox"
                  checked={subscribe.includes(o.name)}
                  onChange={(e) =>
                    setSubscribe((prev) =>
                      e.target.checked
                        ? [...prev, o.name]
                        : prev.filter((s) => s !== o.name),
                    )
                  }
                />
                {o.name} <span style={styles.kind}>({o.kind})</span>
              </label>
            ))}
          </div>
          {elapsed !== null && (
            <p style={styles.meta}>
              Computed in {elapsed.toFixed(0)}ms
              {loading && " (running...)"}
            </p>
          )}
          {error && <p style={styles.error}>{error}</p>}
        </section>

        {stats && (
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
        )}

        {histogram && histogram.length > 0 && (
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
        )}

        {table && table.length > 0 && (
          <section style={{ ...styles.card, gridColumn: "1 / -1" }}>
            <h2 style={styles.cardTitle}>
              Filtered Data ({table.length} rows)
            </h2>
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
        )}
      </div>

      {schema && (
        <footer style={styles.footer}>
          <details>
            <summary style={styles.detailsSummary}>
              Schema (id: {schema.schemaId})
            </summary>
            <pre style={styles.pre}>{JSON.stringify(schema, null, 2)}</pre>
          </details>
        </footer>
      )}
    </div>
  );
}

interface DynamicInputProps {
  input: InputSchema;
  value: unknown;
  onChange: (value: unknown) => void;
}

function DynamicInput({ input, value, onChange }: DynamicInputProps) {
  const ui = input.constraints?.ui;
  const label = (
    <label style={styles.label}>
      {input.description ?? input.name}
      {ui === "slider" && (
        <strong style={{ marginLeft: 6 }}>{String(value)}</strong>
      )}
    </label>
  );

  const node = useMemo(() => {
    if (ui === "slider") {
      return (
        <input
          type="range"
          min={input.constraints?.min as number | undefined}
          max={input.constraints?.max as number | undefined}
          step={(input.constraints?.step as number | undefined) ?? 1}
          value={Number(value ?? 0)}
          onChange={(e) => onChange(Number(e.target.value))}
          style={styles.slider}
        />
      );
    }
    if (ui === "dropdown") {
      const options = (input.constraints?.options as unknown[]) ?? [];
      return (
        <select
          value={String(value ?? "")}
          onChange={(e) => onChange(e.target.value)}
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
          onChange={(e) => onChange(e.target.checked)}
        />
      );
    }
    return (
      <input
        type="text"
        value={String(value ?? "")}
        onChange={(e) => onChange(e.target.value)}
        style={styles.select}
      />
    );
  }, [ui, value, input.constraints, onChange]);

  return (
    <div style={styles.inputGroup}>
      {label}
      {node}
    </div>
  );
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
  slider: { width: "100%" },
  select: {
    width: "100%",
    padding: "0.5rem",
    borderRadius: 6,
    border: "1px solid #dee2e6",
    fontSize: "0.9rem",
  },
  checkbox: {
    display: "flex",
    alignItems: "center",
    gap: "0.4rem",
    marginBottom: "0.3rem",
    fontSize: "0.9rem",
  },
  kind: { color: "#6c757d", fontSize: "0.8rem" },
  meta: { color: "#6c757d", fontSize: "0.85rem", marginTop: "1rem" },
  error: { color: "#dc3545", fontSize: "0.85rem", marginTop: "0.5rem" },
  statsGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(2, 1fr)",
    gap: "1rem",
  },
  statItem: { textAlign: "center" },
  statValue: { fontSize: "1.8rem", fontWeight: 700, color: "#0f3460" },
  statLabel: { fontSize: "0.8rem", color: "#6c757d", textTransform: "uppercase" },
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
};
