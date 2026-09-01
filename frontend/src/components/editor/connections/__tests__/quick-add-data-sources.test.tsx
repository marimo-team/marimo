/* Copyright 2026 Marimo. All rights reserved. */

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { DetectedDataSource } from "@/core/datasets/data-source-discovery";
import { QuickAddDataSources } from "../quick-add-data-sources";

const sources: DetectedDataSource[] = [
  {
    id: "postgres-libpq-environment",
    integration: "postgres",
    category: "database",
    displayName: "PostgreSQL",
    confidence: "high",
    origins: [{ type: "environment", label: "Kernel environment" }],
    configuration: [
      {
        field: "Host",
        value: { kind: "environment-variable", name: "PGHOST" },
      },
      {
        field: "Username",
        value: { kind: "environment-variable", name: "PGUSER" },
      },
      {
        field: "Database",
        value: { kind: "environment-variable", name: "PGDATABASE" },
      },
    ],
    code: "engine = create_engine()",
    hidesWhen: { kind: "dialect", substrings: ["postgres"] },
  },
  {
    id: "pyiceberg-prod",
    integration: "pyiceberg",
    category: "catalog",
    displayName: "PyIceberg (prod)",
    confidence: "high",
    origins: [
      {
        type: "configuration",
        label: "Resolved PyIceberg configuration",
      },
    ],
    configuration: [
      {
        field: "Catalog",
        value: { kind: "safe-literal", value: "prod" },
      },
      {
        field: "Type",
        value: { kind: "safe-literal", value: "REST" },
      },
    ],
    code: 'catalog = load_catalog("prod")',
    hidesWhen: { kind: "dialect", substrings: ["iceberg"] },
  },
];

describe("QuickAddDataSources", () => {
  it("does not render an empty section", () => {
    const { container } = render(
      <QuickAddDataSources sources={[]} onAdd={vi.fn()} />,
    );

    expect(container).toBeEmptyDOMElement();
  });

  it("renders detected sources as clickable tags", () => {
    const onAdd = vi.fn();

    render(<QuickAddDataSources sources={sources} onAdd={onAdd} />);
    fireEvent.click(
      screen.getByRole("button", {
        name: "Add PostgreSQL connection",
      }),
    );

    expect(screen.getByText("Quick add")).toBeInTheDocument();
    expect(onAdd).toHaveBeenCalledWith(sources[0]);
  });

  it("shows environment references on hover", async () => {
    render(<QuickAddDataSources sources={sources} onAdd={vi.fn()} />);
    const tag = screen.getByRole("button", {
      name: "Add PostgreSQL connection",
    });

    fireEvent.pointerMove(tag);
    fireEvent.mouseOver(tag);

    await waitFor(() => {
      expect(screen.getAllByText('os.environ["PGHOST"]')).not.toHaveLength(0);
    });
    expect(screen.getAllByText('os.environ["PGUSER"]')).not.toHaveLength(0);
    expect(screen.getAllByText('os.environ["PGDATABASE"]')).not.toHaveLength(0);
  });

  it("shows safe configuration metadata on hover", async () => {
    render(<QuickAddDataSources sources={sources} onAdd={vi.fn()} />);
    const tag = screen.getByRole("button", {
      name: "Add PyIceberg (prod) connection",
    });

    fireEvent.pointerMove(tag);
    fireEvent.mouseOver(tag);

    await waitFor(() => {
      expect(
        screen.getAllByText("Detected from Resolved PyIceberg configuration"),
      ).not.toHaveLength(0);
    });
    expect(screen.getAllByText("REST")).not.toHaveLength(0);
  });
});
