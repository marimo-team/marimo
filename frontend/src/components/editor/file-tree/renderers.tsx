/* Copyright 2024 Marimo. All rights reserved. */
import { generateColumns } from "@/components/data-table/columns";
import { DataTable } from "@/components/data-table/data-table";
import { parseCsvData } from "@/plugins/impl/vega/loader";
import { Objects } from "@/utils/objects";
import React, { useMemo } from "react";
import { type Base64String, base64ToDataURL } from "@/utils/json/base64";

export const CsvViewer: React.FC<{ contents: string }> = ({ contents }) => {
  const data = useMemo(() => parseCsvData(contents), [contents]);
  const columns = useMemo(
    () =>
      generateColumns({
        items: data,
        rowHeaders: [],
        selection: null,
        showColumnSummaries: false,
      }),
    [data],
  );

  return (
    <DataTable
      data={data}
      columns={columns}
      wrapperClassName="h-full justify-between pb-1 px-1"
      pagination={true}
      pageSize={10}
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
