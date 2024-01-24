/* Copyright 2024 Marimo. All rights reserved. */
import { BarChartBigIcon } from "lucide-react";
import React, { useState } from "react";
import { PRIMITIVE_TYPE_ICON } from "./icons";
import { Schema } from "compassql/build/src/schema";
import { Button } from "@/components/ui/button";

interface Props {
  schema: Schema;
}

const COLUMN_LIMIT = 12;

/**
 * Display component that show the columns in a Compass schema
 * and related stats
 */
export const ColumnSummary: React.FC<Props> = ({ schema }) => {
  const [selectedField, setSelectedField] = useState<string>();
  const [showMore, setShowMore] = useState<boolean>();

  const fields = schema.fieldNames();
  const stats = selectedField
    ? schema.stats({ field: selectedField, channel: "x" })
    : undefined;

  const icon = (
    <BarChartBigIcon
      className="text-muted-foreground"
      width={40}
      height={40}
      strokeWidth={1.5}
    />
  );

  const fieldsToShow = showMore ? fields : fields.slice(0, COLUMN_LIMIT);
  const hasMore = fields.length > COLUMN_LIMIT;

  return (
    <div className="flex flex-col justify-center items-center h-full flex-1 gap-3">
      {icon}
      <span className="text-muted-foreground font-semibold">
        {fields.length > 0 ? fields.length : "No"} fields
      </span>
      <div className="grid grid-cols-3 gap-2 p-2 bg-[var(--slate-1)] border rounded items-center w-fit">
        {fieldsToShow.map((field) => {
          const cardinality = schema.cardinality({
            channel: "x",
            field: field,
          });
          return (
            <div
              key={field}
              className="hover:bg-gray-100 self-start px-2 py-2 rounded flex flex-row gap-2 items-center cursor-pointer justify-center"
              onClick={() => {
                setSelectedField(field);
              }}
            >
              {PRIMITIVE_TYPE_ICON[schema.primitiveType(field)]}
              {field}
              {cardinality > 1 && (
                <span className="text-xs text-muted-foreground">
                  ({cardinality})
                </span>
              )}
            </div>
          );
        })}
        {hasMore && (
          <Button
            variant="link"
            size="sm"
            className="self-center col-span-3 -mt-1"
            onClick={() => setShowMore((v) => !v)}
          >
            {showMore ? "Show less" : "Show more"}
          </Button>
        )}
      </div>
      {selectedField && (
        <div className="grid grid-cols-4 gap-2 p-2">
          {STAT_KEYS.map((key) => (
            <div key={key} className="flex flex-row gap-2 min-w-[100px]">
              <span className="font-semibold">{key}</span>
              <span>{formatStat(stats?.[key])}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

const STAT_KEYS = [
  "distinct",
  "min",
  "max",
  "mean",
  "median",
  "q1",
  "q3",
  "stdev",
];

function formatStat(value: unknown) {
  if (typeof value === "number") {
    // Decimal .2
    return new Intl.NumberFormat("en-US", {
      maximumFractionDigits: 2,
    }).format(value);
  }
  if (typeof value === "string") {
    return value;
  }
  if (typeof value === "object" && value instanceof Date) {
    // Just day, month, year
    return new Intl.DateTimeFormat("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
    }).format(value);
  }

  return String(value);
}
