/* Copyright 2024 Marimo. All rights reserved. */
import {
  generateColumns,
  inferFieldTypes,
} from "@/components/data-table/columns";
import { DataTable } from "@/components/data-table/data-table";
import { parseCsvData } from "@/plugins/impl/vega/loader";
import { Objects } from "@/utils/objects";
import type React from "react";
import { useMemo, useState } from "react";
import { type Base64String, base64ToDataURL } from "@/utils/json/base64";
import type { PaginationState } from "@tanstack/react-table";
import { Arrays } from "@/utils/arrays";

const PAGE_SIZE = 25;

export const CsvViewer: React.FC<{ contents: string }> = ({ contents }) => {
  const data = useMemo(() => parseCsvData(contents), [contents]);
  const [pagination, setPagination] = useState<PaginationState>({
    pageIndex: 0,
    pageSize: PAGE_SIZE,
  });
  const fieldTypes = useMemo(() => inferFieldTypes(data), [data]);
  const columns = useMemo(
    () =>
      generateColumns<object>({
        rowHeaders: Arrays.EMPTY,
        selection: null,
        fieldTypes,
      }),
    [fieldTypes],
  );

  return (
    <DataTable<object>
      data={data}
      totalRows={data.length}
      columns={columns}
      totalColumns={columns.length}
      manualPagination={false}
      paginationState={pagination}
      setPaginationState={setPagination}
      wrapperClassName="h-full justify-between pb-1 px-1"
      pagination={true}
      className="rounded-none border-b flex overflow-hidden"
      rowSelection={Objects.EMPTY}
    />
  );
};
export const ImageViewer: React.FC<{ base64: Base64String; mime: string }> = ({
  mime,
  base64,
}) => {
  return <img src={base64ToDataURL(base64, mime)} alt="Preview" />;
};

export const AudioViewer: React.FC<{ base64: Base64String; mime: string }> = ({
  mime,
  base64,
}) => {
  // eslint-disable-next-line jsx-a11y/media-has-caption
  return <audio controls={true} src={base64ToDataURL(base64, mime)} />;
};

export const VideoViewer: React.FC<{ base64: Base64String; mime: string }> = ({
  mime,
  base64,
}) => {
  // eslint-disable-next-line jsx-a11y/media-has-caption
  return <video controls={true} src={base64ToDataURL(base64, mime)} />;
};
