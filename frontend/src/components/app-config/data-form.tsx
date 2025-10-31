/* Copyright 2024 Marimo. All rights reserved. */

import type { ChangeEvent } from "react";
import type { FieldPath, UseFormReturn } from "react-hook-form";
import {
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { NativeSelect } from "@/components/ui/native-select";
import { NumberField } from "@/components/ui/number-field";
import type { UserConfig } from "@/core/config/config-schema";
import {
  formItemClasses,
  SettingGroup,
  SQL_OUTPUT_SELECT_OPTIONS,
} from "./common";
import { IsOverridden } from "./is-overridden";

const DISCOVERY_OPTIONS = ["auto", "true", "false"];

export const DataForm = ({
  form,
  config,
  onSubmit,
}: {
  form: UseFormReturn<UserConfig>;
  config: UserConfig;
  onSubmit: (values: UserConfig) => void;
}) => {
  const renderDiscoveryForm = (name: FieldPath<UserConfig>, label: string) => {
    return (
      <FormField
        control={form.control}
        name={name}
        render={({ field }) => {
          const onChange = (e: ChangeEvent<HTMLSelectElement>) => {
            const value = e.target.value;
            field.onChange(
              value === "true" ? true : value === "false" ? false : value,
            );
          };
          return (
            <FormItem className={formItemClasses}>
              <FormLabel className="text-sm font-normal w-16">
                {label}
              </FormLabel>
              <FormControl>
                <NativeSelect
                  data-testid="auto-discover-schemas-select"
                  onChange={onChange}
                  value={
                    field.value === undefined ? "auto" : field.value.toString()
                  }
                  disabled={field.disabled}
                  className="w-[100px]"
                >
                  {DISCOVERY_OPTIONS.map((option) => (
                    <option value={option} key={option}>
                      {option}
                    </option>
                  ))}
                </NativeSelect>
              </FormControl>
              <IsOverridden userConfig={config} name={name} />
            </FormItem>
          );
        }}
      />
    );
  };

  return (
    <>
      <FormField
        control={form.control}
        name="display.dataframes"
        render={({ field }) => (
          <div className="flex flex-col space-y-1">
            <FormItem className={formItemClasses}>
              <FormLabel>Dataframe viewer</FormLabel>
              <FormControl>
                <NativeSelect
                  data-testid="display-dataframes-select"
                  onChange={(e) => field.onChange(e.target.value)}
                  value={field.value}
                  disabled={field.disabled}
                  className="inline-flex mr-2"
                >
                  {["rich", "plain"].map((option) => (
                    <option value={option} key={option}>
                      {option}
                    </option>
                  ))}
                </NativeSelect>
              </FormControl>
              <FormMessage />
              <IsOverridden userConfig={config} name="display.dataframes" />
            </FormItem>

            <FormDescription>
              Whether to use marimo's rich dataframe viewer or a plain HTML
              table. This requires restarting your notebook to take effect.
            </FormDescription>
          </div>
        )}
      />
      <FormField
        control={form.control}
        name="display.default_table_page_size"
        render={({ field }) => (
          <div className="flex flex-col space-y-1">
            <FormItem className={formItemClasses}>
              <FormLabel>Default table page size</FormLabel>
              <FormControl>
                <NumberField
                  aria-label="Default table page size"
                  data-testid="default-table-page-size-input"
                  className="m-0 w-24"
                  {...field}
                  value={field.value}
                  minValue={1}
                  step={1}
                  onChange={(value) => {
                    field.onChange(value);
                    if (!Number.isNaN(value)) {
                      onSubmit(form.getValues());
                    }
                  }}
                />
              </FormControl>
              <FormMessage />
              <IsOverridden
                userConfig={config}
                name="display.default_table_page_size"
              />
            </FormItem>
            <FormDescription>
              The default number of rows displayed in dataframes and SQL
              results.
            </FormDescription>
          </div>
        )}
      />
      <FormField
        control={form.control}
        name="display.default_table_max_columns"
        render={({ field }) => (
          <div className="flex flex-col space-y-1">
            <FormItem className={formItemClasses}>
              <FormLabel>Default table max columns</FormLabel>
              <FormControl>
                <NumberField
                  aria-label="Default table max columns"
                  data-testid="default-table-max-columns-input"
                  className="m-0 w-24"
                  {...field}
                  value={field.value}
                  minValue={1}
                  step={1}
                  onChange={(value) => {
                    field.onChange(value);
                    if (!Number.isNaN(value)) {
                      onSubmit(form.getValues());
                    }
                  }}
                />
              </FormControl>
              <FormMessage />
              <IsOverridden
                userConfig={config}
                name="display.default_table_max_columns"
              />
            </FormItem>
            <FormDescription>
              The default maximum number of columns displayed in dataframes and
              SQL results.
            </FormDescription>
          </div>
        )}
      />

      <SettingGroup title="SQL">
        <div className="flex flex-col gap-1">
          <div className="text-sm text-foreground">
            Database Schema Discovery
          </div>
          <div className="text-sm text-muted-foreground mb-2">
            Whether database schemas, tables, and columns are automatically
            discovered.
            <br />
            <span className="font-semibold">
              Can be expensive for large databases.
            </span>{" "}
            Use 'auto' to determine introspection based on the{" "}
            <a
              className="text-link hover:underline"
              rel="noopener noreferrer"
              target="_blank"
              href="https://docs.marimo.io/guides/working_with_data/sql/?h=database#database-schema-and-table-auto-discovery"
            >
              database
            </a>
            .
          </div>

          {renderDiscoveryForm("datasources.auto_discover_schemas", "Schemas")}
          {renderDiscoveryForm("datasources.auto_discover_tables", "Tables")}
          {renderDiscoveryForm("datasources.auto_discover_columns", "Columns")}
        </div>

        {/* TODO: Issue with frontend being stuck */}
        {/* <FormField
          control={form.control}
          name="diagnostics.sql_linter"
          render={({ field }) => (
            <div className="flex flex-col space-y-1">
              <FormItem className={formItemClasses}>
                <FormLabel>SQL Linter</FormLabel>
                <FormControl>
                  <Checkbox
                    data-testid="sql-linter-checkbox"
                    checked={field.value}
                    onCheckedChange={field.onChange}
                  />
                </FormControl>
                <FormMessage />
                <IsOverridden
                  userConfig={config}
                  name="diagnostics.sql_linter"
                />
              </FormItem>
              <FormDescription>
                Better linting and autocompletions for SQL cells.
              </FormDescription>
            </div>
          )}
        /> */}

        <FormField
          control={form.control}
          name="runtime.default_sql_output"
          render={({ field }) => (
            <div className="flex flex-col space-y-1">
              <FormItem className={formItemClasses}>
                <FormLabel>Default SQL output</FormLabel>
                <FormControl>
                  <NativeSelect
                    data-testid="user-config-sql-output-select"
                    onChange={(e) => field.onChange(e.target.value)}
                    value={field.value}
                    disabled={field.disabled}
                    className="inline-flex mr-2"
                  >
                    {SQL_OUTPUT_SELECT_OPTIONS.map((option) => (
                      <option value={option.value} key={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </NativeSelect>
                </FormControl>
                <FormMessage />
                <IsOverridden
                  userConfig={config}
                  name="runtime.default_sql_output"
                />
              </FormItem>

              <FormDescription>
                The default SQL output type for new notebooks; overridden by
                "sql_output" in the application config.
              </FormDescription>
            </div>
          )}
        />
      </SettingGroup>
    </>
  );
};
