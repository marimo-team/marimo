/* Copyright 2024 Marimo. All rights reserved. */
import { DataTable } from "@/components/data-table/data-table";
import { generateColumns } from "@/components/data-table/columns";

export default {
  title: "DataTable",
  component: DataTable,
};

export const Default = {
  render: () => (
    <DataTable
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
      columns={generateColumns(
        [
          {
            first_name: "Michael",
            last_name: "Scott",
          },
          {
            first_name: "Dwight",
            last_name: "Schrute",
          },
        ],
        [],
        null,
      )}
    />
  ),

  name: "Default",
};

export const Empty1 = {
  render: () => (
    <DataTable
      data={[]}
      columns={generateColumns(
        [
          {
            first_name: "Michael",
            last_name: "Scott",
          },
          {
            first_name: "Dwight",
            last_name: "Schrute",
          },
        ],
        [],
        null,
      )}
    />
  ),

  name: "Empty 1",
};

export const Empty2 = {
  render: () => <DataTable data={[]} columns={[]} />,
  name: "Empty 2",
};

export const Pagination = {
  render: () => (
    <DataTable
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
      columns={generateColumns(
        [
          {
            first_name: "Michael",
            last_name: "Scott",
          },
          {
            first_name: "Dwight",
            last_name: "Schrute",
          },
        ],
        [],
        null,
      )}
      pagination={true}
    />
  ),

  name: "Pagination",
};
