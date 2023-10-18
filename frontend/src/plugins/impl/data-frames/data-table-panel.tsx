/* Copyright 2023 Marimo. All rights reserved. */
import { generateColumns } from "@/components/data-table/columns";
import { DataTable } from "@/components/data-table/data-table";
import { Functions } from "@/utils/functions";
import React, { useMemo } from "react";
import { T } from "vitest/dist/reporters-5f784f42";

interface Props {
  data: T[];
}

export const DataTablePanel: React.FC<Props> = ({ data }) => {
  const columns = useMemo(() => generateColumns(data, null), [data]);

  if (!data) {
    return null;
  }

  return (
    <DataTable
      data={data}
      columns={columns}
      pagination={true}
      selection={null}
      rowSelection={{}}
      onRowSelectionChange={Functions.NOOP}
    />
  );
};
