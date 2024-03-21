/* Copyright 2024 Marimo. All rights reserved. */
import { BarChartBigIcon } from "lucide-react";
import React, { useState } from "react";
import { PRIMITIVE_TYPE_ICON } from "./icons";
import { Schema } from "compassql/build/src/schema";
import { Button } from "@/components/ui/button";
import { cn } from "@/utils/cn";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

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
    <div className="flex flex-col justify-center items-center h-full flex-1 gap-2">
      {icon}
      <span className="text-muted-foreground font-semibold">
        {fields.length > 0 ? fields.length : "No"} fields
      </span>
      <div className="hidden lg:grid grid-cols-2 xl:grid-cols-3 gap-2 p-2 bg-[var(--slate-1)] border rounded lg:items-center items-start w-fit grid-flow-dense max-h-[300px] overflow-auto">
        {fieldsToShow.map((field) => {
          const cardinality = schema.cardinality({
            channel: "x",
            field: field,
          });
          return (
            <span
              key={field}
              className={cn(
                "hover:bg-muted self-start px-2 py-2 rounded flex flex-row gap-1 items-center cursor-pointer lg:justify-center text-sm truncate flex-shrink-0 overflow-hidden",
                selectedField === field && "bg-muted",
              )}
              onClick={() => {
                if (selectedField === field) {
                  setSelectedField(undefined);
                  return;
                }
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
            </span>
          );
        })}
        {hasMore && (
          <Button
            data-testid="marimo-plugin-data-explorer-show-more-columns"
            variant="link"
            size="sm"
            className="self-center col-span-3 -mt-1"
            onClick={() => setShowMore((v) => !v)}
          >
            {showMore ? "Show less" : "Show more"}
          </Button>
        )}
      </div>
      <div className="lg:hidden">
        <Select
          data-testid="marimo-plugin-data-explorer-column-select"
          value={selectedField || ""}
          disabled={fields.length === 0}
          onValueChange={(value) => {
            setSelectedField(value);
          }}
        >
          <SelectTrigger className="min-w-[210px] h-full">
            <SelectValue placeholder="Select a column" />
          </SelectTrigger>
          <SelectContent>
            <SelectGroup>
              {schema.fieldNames().map((name) => {
                return (
                  <SelectItem key={name} value={name.toString()}>
                    <span className="flex items-center gap-2 flex-1">
                      {PRIMITIVE_TYPE_ICON[schema.primitiveType(name)]}
                      <span className="flex-1">{name}</span>
                      <span className="text-muted-foreground text-xs font-semibold">
                        ({schema.vlType(name)})
                      </span>
                    </span>
                  </SelectItem>
                );
              })}
            </SelectGroup>
          </SelectContent>
        </Select>
      </div>
      {selectedField && (
        <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-2 p-2 text-sm">
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
