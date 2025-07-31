/* Copyright 2024 Marimo. All rights reserved. */

import {
  generateColumns,
  inferFieldTypes,
} from "@/components/data-table/columns";
import { DataTable } from "@/components/data-table/data-table";
import { Functions } from "@/utils/functions";

export default {
  title: "DataTable",
  component: DataTable,
};

export const Default = {
  render: () => (
    <DataTable
      totalRows={100}
      totalColumns={2}
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
        fieldTypes: inferFieldTypes([
          {
            first_name: "Michael",
            last_name: "Scott",
          },
          {
            first_name: "Dwight",
            last_name: "Schrute",
          },
        ]),
        rowHeaders: [],
        selection: null,
      })}
    />
  ),

  name: "Default",
};

export const Empty1 = {
  render: () => (
    <DataTable
      totalRows={100}
      totalColumns={2}
      paginationState={{ pageIndex: 0, pageSize: 10 }}
      setPaginationState={Functions.NOOP}
      data={[]}
      columns={generateColumns({
        fieldTypes: inferFieldTypes([
          {
            first_name: "Michael",
            last_name: "Scott",
          },
          {
            first_name: "Dwight",
            last_name: "Schrute",
          },
        ]),
        rowHeaders: [],
        selection: null,
      })}
    />
  ),

  name: "Empty 1",
};

export const Empty2 = {
  render: () => (
    <DataTable
      totalRows={100}
      totalColumns={2}
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
      totalColumns={2}
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
        fieldTypes: inferFieldTypes([
          {
            first_name: "Michael",
            last_name: "Scott",
          },
          {
            first_name: "Dwight",
            last_name: "Schrute",
          },
        ]),
        rowHeaders: [],
        selection: null,
      })}
      pagination={true}
    />
  ),

  name: "Pagination",
};
