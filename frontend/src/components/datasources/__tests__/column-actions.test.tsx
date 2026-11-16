/* Copyright 2026 Marimo. All rights reserved. */

import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { createStore, Provider } from "jotai";
import { beforeAll, describe, expect, it, vi } from "vitest";
import { MockRequestClient } from "@/__mocks__/requests";
import { Command, CommandList } from "@/components/ui/command";
import { TooltipProvider } from "@/components/ui/tooltip";
import type { DataTable } from "@/core/kernel/messages";
import { requestClientAtom } from "@/core/network/requests";
import { copyToClipboard } from "@/utils/copy";
import { TableList } from "../datasources";

vi.mock("@/utils/copy", () => ({
  copyToClipboard: vi.fn().mockResolvedValue(undefined),
}));

beforeAll(() => {
  HTMLElement.prototype.scrollIntoView = vi.fn();
});

const table: DataTable = {
  name: "users",
  columns: [
    {
      name: "email",
      type: "string",
      external_type: "VARCHAR",
      sample_values: [],
    },
    {
      name: "name",
      type: "string",
      external_type: "VARCHAR",
      sample_values: [],
    },
  ],
  source: "memory",
  source_type: "local",
  type: "table",
  engine: null,
  indexes: null,
  num_columns: 2,
  num_rows: null,
  variable_name: null,
  primary_keys: null,
};

describe("Column actions", () => {
  it("copies each column through one named button without expanding its preview", async () => {
    const store = createStore();
    const client = MockRequestClient.create();
    store.set(requestClientAtom, client);
    render(
      <Provider store={store}>
        <TooltipProvider>
          <Command>
            <CommandList>
              <TableList tables={[table]} />
            </CommandList>
          </Command>
        </TooltipProvider>
      </Provider>,
    );

    fireEvent.click(await screen.findByText("users"));

    for (const column of table.columns) {
      const copyButton = await screen.findByRole("button", {
        name: `Copy column name ${column.name}`,
      });
      const row = screen.getByRole("option", {
        name: `${column.name} ${column.external_type}`,
      });
      expect(within(row).getAllByRole("button")).toEqual([copyButton]);
      expect(copyButton.querySelector("button")).toBeNull();

      fireEvent.focus(copyButton);
      expect(
        await screen.findByRole("tooltip", { name: "Copy column name" }),
      ).toBeInTheDocument();

      fireEvent.click(copyButton);
      await waitFor(() => {
        expect(copyToClipboard).toHaveBeenLastCalledWith(column.name);
      });
      expect(client.previewDatasetColumn).not.toHaveBeenCalled();
    }
    expect(copyToClipboard).toHaveBeenCalledTimes(2);
  });
});
