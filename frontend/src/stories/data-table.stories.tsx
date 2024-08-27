/* Copyright 2024 Marimo. All rights reserved. */
import { DataTable } from "@/components/data-table/data-table";
import { generateColumns } from "@/components/data-table/columns";
import { Functions } from "@/utils/functions";

export default {
  title: "DataTable",
  component: DataTable,
};

export const Default = {
  render: () => (
    <DataTable
      totalRows={100}
      paginationState={{ pageIndex: 0, pageSize: 10 }}
      setPaginationState={Functions.NOOP}
      data={[
        {
          first_name: "Michael",
          last_name: "Scott",
        },
        {
          first_name: "Dwight",
          last_name: "Schrute",
        },
      ]}
      columns={generateColumns({
        items: [
          {
            first_name: "Michael",
            last_name: "Scott",
          },
          {
            first_name: "Dwight",
            last_name: "Schrute",
          },
        ],
        rowHeaders: [],
        selection: null,
        showColumnSummaries: false,
      })}
    />
  ),

  name: "Default",
};

export const Empty1 = {
  render: () => (
    <DataTable
      totalRows={100}
      paginationState={{ pageIndex: 0, pageSize: 10 }}
      setPaginationState={Functions.NOOP}
      data={[]}
      columns={generateColumns({
        items: [
          {
            first_name: "Michael",
            last_name: "Scott",
          },
          {
            first_name: "Dwight",
            last_name: "Schrute",
          },
        ],
        rowHeaders: [],
        selection: null,
        showColumnSummaries: false,
      })}
    />
  ),

  name: "Empty 1",
};

export const Empty2 = {
  render: () => (
    <DataTable
      totalRows={100}
      paginationState={{ pageIndex: 0, pageSize: 10 }}
      setPaginationState={Functions.NOOP}
      data={[]}
      columns={[]}
    />
  ),
  name: "Empty 2",
};

export const Pagination = {
  render: () => (
    <DataTable
      totalRows={100}
      paginationState={{ pageIndex: 0, pageSize: 10 }}
      setPaginationState={Functions.NOOP}
      data={[
        {
          first_name: "Michael",
          last_name: "Scott",
        },
        {
          first_name: "Dwight",
          last_name: "Schrute",
        },
      ]}
      columns={generateColumns({
        items: [
          {
            first_name: "Michael",
            last_name: "Scott",
          },
          {
            first_name: "Dwight",
            last_name: "Schrute",
          },
        ],
        rowHeaders: [],
        selection: null,
        showColumnSummaries: false,
      })}
      pagination={true}
    />
  ),

  name: "Pagination",
};
