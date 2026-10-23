/* Copyright 2026 Marimo. All rights reserved. */

import { render, screen, waitFor } from "@testing-library/react";
import { Provider } from "jotai";
import type React from "react";
import { describe, expect, it } from "vitest";
import { MockRequestClient } from "@/__mocks__/requests";
import type { SQLTableContext } from "@/core/datasets/data-source-connections";
import { PreviewSQLTableList } from "@/core/datasets/request-registry";
import type { SQLTableListPreview } from "@/core/kernel/messages";
import type { RequestId } from "@/core/network/DeferredRequestRegistry";
import { requestClientAtom } from "@/core/network/requests";
import { store } from "@/core/state/jotai";
import { TableList } from "../datasources";

const wrapper = ({ children }: { children: React.ReactNode }) => (
  <Provider store={store}>{children}</Provider>
);

const sqlTableContext: SQLTableContext = {
  engine: "my_engine",
  database: "my_db",
  schema: "public",
  dialect: "postgres",
  schemaPath: ["public"],
};

// The kernel answers table-list requests over the websocket, so the mock
// settles the deferred request instead of returning the response directly.
function renderDeferredTableList(settle?: (requestId: RequestId) => void) {
  const client = MockRequestClient.create();
  client.previewSQLTableList.mockImplementation(async ({ requestId }) => {
    settle?.(requestId);
    return null;
  });
  store.set(requestClientAtom, client);
  render(
    <TableList
      tables={[]}
      tablesResolved={false}
      sqlTableContext={sqlTableContext}
    />,
    { wrapper },
  );
  return client;
}

describe("TableList deferred discovery", () => {
  it("shows the error when the request rejects", async () => {
    renderDeferredTableList((requestId) =>
      PreviewSQLTableList.reject(requestId, new Error("engine offline")),
    );

    expect(screen.getByText("Loading tables...")).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText("engine offline")).toBeInTheDocument();
    });
    expect(screen.queryByText("Loading tables...")).toBeNull();
  });

  it("shows the error when the response has no tables field", async () => {
    renderDeferredTableList((requestId) =>
      PreviewSQLTableList.resolve(requestId, {} as SQLTableListPreview),
    );

    await waitFor(() => {
      expect(screen.getByText("No tables available")).toBeInTheDocument();
    });
    expect(screen.queryByText("Loading tables...")).toBeNull();
  });

  it("shows the empty state for an empty table list", async () => {
    renderDeferredTableList((requestId) =>
      PreviewSQLTableList.resolve(requestId, {
        tables: [],
      } as unknown as SQLTableListPreview),
    );

    await waitFor(() => {
      expect(screen.getByText("No tables found")).toBeInTheDocument();
    });
    expect(screen.queryByText("Loading tables...")).toBeNull();
  });

  it("requests the table list with the table context and waits for the kernel", async () => {
    const client = renderDeferredTableList();

    await waitFor(() => {
      expect(client.previewSQLTableList).toHaveBeenCalledTimes(1);
    });
    expect(client.previewSQLTableList).toHaveBeenCalledWith(
      expect.objectContaining({
        engine: "my_engine",
        database: "my_db",
        schema: "public",
        schemaPath: ["public"],
      }),
    );
    expect(screen.getByText("Loading tables...")).toBeInTheDocument();
  });
});
