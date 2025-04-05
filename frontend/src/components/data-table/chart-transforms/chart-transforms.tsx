/* Copyright 2024 Marimo. All rights reserved. */

import React, { useState, useMemo } from "react";
import { Button } from "@/components/ui/button";
import {
  BarChartIcon,
  ChartBarIcon,
  LineChartIcon,
  PieChartIcon,
  TableIcon,
} from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

import { Tabs, TabsTrigger, TabsList, TabsContent } from "@/components/ui/tabs";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../../ui/select";
import type { z } from "zod";
import { useForm, type UseFormReturn } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { LineChartSchema } from "./chart-schemas";
import {
  Form,
  FormControl,
  FormLabel,
  FormField,
  FormItem,
} from "@/components/ui/form";
import { DebouncedInput } from "@/components/ui/input";
import { getDefaults } from "@/components/forms/form-utils";
import { useLastFocusedCellId } from "@/core/cells/focus";
import { useAtom } from "jotai";
import { findActiveCellId } from "@/core/cells/ids";
import { debounce } from "lodash-es";
import { type TabName, tabsStorageAtom, type ChartType } from "./storage";
import type { FieldTypesWithExternalType } from "../types";
import { DATA_TYPE_ICON } from "@/components/datasets/icons";
import type { DataType } from "@/core/kernel/messages";
import { useAsyncData } from "@/hooks/useAsyncData";
import { vegaLoadData } from "@/plugins/impl/vega/loader";
import type { GetDataUrl } from "@/plugins/impl/DataTablePlugin";
import { createVegaSpec } from "./chart-spec";
import { type ResolvedTheme, useTheme } from "@/theme/useTheme";
import { compile } from "vega-lite";
import type { Spec } from "vega";

const LazyVegaLite = React.lazy(() =>
  import("react-vega").then((m) => ({ default: m.VegaLite })),
);

const NEW_TAB_NAME = "Chart" as TabName;
const NEW_CHART_TYPE = "line" as ChartType;

export interface TablePanelProps {
  dataTable: JSX.Element;
  getDataUrl: GetDataUrl;
  fieldTypes?: FieldTypesWithExternalType | null;
}

// todo: change from jsx.element
export const TablePanel: React.FC<TablePanelProps> = ({
  dataTable,
  getDataUrl,
  fieldTypes,
}) => {
  const [tabs, saveTabs] = useAtom(tabsStorageAtom);

  // const [domCellId, setDomCellId] = useState<CellId | null>(null);
  const lastFocusedCellId = useLastFocusedCellId();

  // This isn't finding the correct cell
  const activeCellId = findActiveCellId();
  const cellId = activeCellId || lastFocusedCellId;

  const handleAddTab = () => {
    if (!cellId) {
      return;
    }
    saveTabs([
      ...tabs,
      {
        cellId,
        tabName: NEW_TAB_NAME,
        chartType: NEW_CHART_TYPE,
        config: getDefaults(LineChartSchema),
      },
    ]);
  };

  const handleDeleteTab = (tabName: TabName) => {
    if (!cellId) {
      return;
    }
    saveTabs(tabs.filter((tab) => tab.tabName !== tabName));
  };

  const saveTabChart = (
    tabName: TabName,
    chartType: ChartType,
    chartConfig: z.infer<typeof LineChartSchema>,
  ) => {
    if (!cellId) {
      return;
    }

    const updatedTabs = [...tabs];
    const existingIndex = tabs.findIndex(
      (tab) => tab.tabName === tabName && tab.cellId === cellId,
    );

    if (existingIndex >= 0) {
      updatedTabs[existingIndex] = {
        ...updatedTabs[existingIndex],
        config: chartConfig,
      };
    } else {
      updatedTabs.push({
        cellId,
        tabName,
        chartType,
        config: chartConfig,
      });
    }

    saveTabs(updatedTabs);
  };

  const saveTabChartType = (tabName: TabName, chartType: ChartType) => {
    if (!cellId) {
      return;
    }
    saveTabs(
      tabs.map((tab) =>
        tab.tabName === tabName && tab.cellId === cellId
          ? { ...tab, chartType }
          : tab,
      ),
    );
  };

  return (
    <Tabs defaultValue="table">
      <TabsList>
        <TabsTrigger className="text-xs py-1" value="table">
          <TableIcon className="w-3 h-3 mr-2" />
          Table
        </TabsTrigger>
        {tabs.map((tab, idx) => (
          <TabsTrigger key={idx} className="text-xs py-1" value={tab.tabName}>
            {tab.tabName}
            <span
              className="ml-1.5 hover:font-bold"
              onClick={(e) => {
                e.stopPropagation();
                handleDeleteTab(tab.tabName);
              }}
            >
              X
            </span>
          </TabsTrigger>
        ))}
        <DropdownMenu>
          <DropdownMenuTrigger asChild={true}>
            <Button variant="text" size="icon">
              +
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent>
            <DropdownMenuItem onClick={handleAddTab}>
              <ChartBarIcon className="w-3 h-3 mr-2" />
              Add chart
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </TabsList>

      <TabsContent className="mt-1 overflow-hidden" value="table">
        {dataTable}
      </TabsContent>
      {tabs.map((tab, idx) => {
        const saveChart = (formValues: z.infer<typeof LineChartSchema>) => {
          saveTabChart(tab.tabName, tab.chartType, formValues);
        };
        const saveChartType = (chartType: ChartType) => {
          saveTabChartType(tab.tabName, chartType);
        };
        return (
          <TabsContent key={idx} value={tab.tabName} className="h-[400px] mt-1">
            <ChartPanel
              chartConfig={tab.config}
              chartType={tab.chartType}
              saveChart={saveChart}
              saveChartType={saveChartType}
              getDataUrl={getDataUrl}
              fieldTypes={fieldTypes}
            />
          </TabsContent>
        );
      })}
    </Tabs>
  );
};

export const ChartPanel: React.FC<{
  chartConfig: z.infer<typeof LineChartSchema> | null;
  chartType: ChartType;
  saveChart: (formValues: z.infer<typeof LineChartSchema>) => void;
  saveChartType: (chartType: ChartType) => void;
  getDataUrl: GetDataUrl;
  fieldTypes?: FieldTypesWithExternalType | null;
}> = ({
  chartConfig,
  chartType,
  saveChart,
  saveChartType,
  getDataUrl,
  fieldTypes,
}) => {
  const form = useForm<z.infer<typeof LineChartSchema>>({
    defaultValues: chartConfig ?? getDefaults(LineChartSchema),
    resolver: zodResolver(LineChartSchema),
  });

  // Simplified to just track chart type
  const [chartTypeSelected, setChartTypeSelected] =
    useState<ChartType>(chartType);

  const { data, loading, error } = useAsyncData(async () => {
    const response = await getDataUrl({});
    const chartData = await vegaLoadData(
      response.data_url,
      {
        type: "json",
      },
      {
        replacePeriod: true,
      },
    );
    return chartData;
  }, []);

  const formValues = form.watch();

  // This ensures the chart re-renders when the actual values change
  const memoizedFormValues = useMemo(() => {
    return structuredClone(formValues);
  }, [formValues]);

  // Memoize the Chart component to prevent unnecessary re-renders
  const Chart = useMemo(() => {
    if (loading) {
      return <div>Loading...</div>;
    }
    if (error) {
      return <div>Error: {error.message}</div>;
    }
    return <LineChart formValues={memoizedFormValues} data={data} />;
  }, [loading, error, memoizedFormValues, data]);

  return (
    <div className="flex flex-row gap-6 p-3 h-full rounded-md border overflow-auto">
      <div className="flex flex-col gap-3">
        <Select
          value={chartTypeSelected}
          onValueChange={(value) => {
            setChartTypeSelected(value as ChartType);
            saveChartType(value as ChartType);
          }}
        >
          <div className="flex flex-col gap-1">
            <span className="text-sm">Visualization Type</span>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="line" className="gap-2">
                <div className="flex items-center">
                  <LineChartIcon className="w-4 h-4 mr-2" />
                  Line
                </div>
              </SelectItem>
              <SelectItem value="bar">
                <div className="flex items-center">
                  <BarChartIcon className="w-4 h-4 mr-2" />
                  Bar
                </div>
              </SelectItem>
              <SelectItem value="pie">
                <div className="flex items-center">
                  <PieChartIcon className="w-4 h-4 mr-2" />
                  Pie
                </div>
              </SelectItem>
            </SelectContent>
          </div>
        </Select>

        <LineChartForm
          form={form}
          saveChart={saveChart}
          fieldTypes={fieldTypes}
        />
      </div>

      <div className="m-auto">{Chart}</div>
    </div>
  );
};

interface ChartFormProps {
  form: UseFormReturn<z.infer<typeof LineChartSchema>>;
  saveChart: (formValues: z.infer<typeof LineChartSchema>) => void;
  fieldTypes?: FieldTypesWithExternalType | null;
}

const LineChartForm = ({ form, saveChart, fieldTypes }: ChartFormProps) => {
  const fields = fieldTypes?.map((field) => {
    return {
      name: field[0],
      type: field[1][0],
    };
  });

  // Create a debounced save function that will be called when form values change
  const debouncedSave = useMemo(
    () =>
      debounce(
        (values: z.infer<typeof LineChartSchema>) => saveChart(values),
        300,
      ),
    [saveChart],
  );

  return (
    <Form {...form}>
      <form
        onSubmit={(e) => e.preventDefault()}
        onChange={() => {
          // Get the latest form values and save them
          const values = form.getValues();
          debouncedSave(values);
        }}
      >
        <Tabs defaultValue="general">
          <TabsList>
            <TabsTrigger value="general">General</TabsTrigger>
            <TabsTrigger value="x-axis">X-Axis</TabsTrigger>
            <TabsTrigger value="y-axis">Y-Axis</TabsTrigger>
          </TabsList>
          <TabsContent value="general" className="flex flex-col gap-2">
            <FormField
              control={form.control}
              name="general.xColumn.name"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>X column</FormLabel>
                  <FormControl>
                    <Select
                      {...field}
                      onValueChange={(value) => {
                        const column = fields?.find(
                          (column) => column.name === value,
                        );
                        if (column) {
                          form.setValue("general.xColumn.type", column.type);
                        }
                        form.setValue("general.xColumn.name", value);
                      }}
                      value={field.value ?? ""}
                    >
                      <SelectTrigger className="w-40">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {fields?.map((column) => {
                          const DataTypeIcon = DATA_TYPE_ICON[column.type];
                          return (
                            <SelectItem key={column.name} value={column.name}>
                              <div className="flex items-center">
                                <DataTypeIcon className="w-3 h-3 mr-2" />
                                {column.name}
                              </div>
                            </SelectItem>
                          );
                        })}
                      </SelectContent>
                    </Select>
                  </FormControl>
                </FormItem>
              )}
            />
            <ColumnFormField
              form={form}
              formLabel="Y column"
              formFieldName="general.yColumn"
              columnFields={fields}
            />
          </TabsContent>
          <TabsContent value="x-axis">
            <FormField
              control={form.control}
              name="xAxis.label"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>X-axis Label</FormLabel>
                  <FormControl>
                    <DebouncedInput
                      {...field}
                      value={field.value ?? ""}
                      onValueChange={field.onChange}
                    />
                  </FormControl>
                </FormItem>
              )}
            />
          </TabsContent>
          <TabsContent value="y-axis">
            <FormField
              control={form.control}
              name="yAxis.label"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Y-axis Label</FormLabel>
                  <FormControl>
                    <DebouncedInput
                      {...field}
                      value={field.value ?? ""}
                      onValueChange={field.onChange}
                    />
                  </FormControl>
                </FormItem>
              )}
            />
          </TabsContent>
        </Tabs>
      </form>
    </Form>
  );
};

const ColumnFormField = ({
  form,
  formLabel,
  formFieldName,
  columnFields,
}: {
  form: UseFormReturn<z.infer<typeof LineChartSchema>>;
  formLabel: string;
  formFieldName:
    | "general.xColumn"
    | "general.yColumn"
    | "xAxis.label"
    | "yAxis.label";
  columnFields?: Array<{ name: string; type: DataType }>;
}) => {
  return (
    <FormField
      control={form.control}
      name={formFieldName}
      render={({ field }) => {
        // Safely extract the value to use in the Select
        const selectValue =
          field.value && typeof field.value === "object"
            ? field.value.name
            : field.value || "";

        return (
          <FormItem>
            <FormLabel>{formLabel}</FormLabel>
            <FormControl>
              <Select onValueChange={field.onChange} value={selectValue}>
                <SelectTrigger className="w-40">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {columnFields?.map((column) => {
                    const DataTypeIcon = DATA_TYPE_ICON[column.type];
                    return (
                      <SelectItem key={column.name} value={column.name}>
                        <div className="flex items-center">
                          <DataTypeIcon className="w-3 h-3 mr-2" />
                          {column.name}
                        </div>
                      </SelectItem>
                    );
                  })}
                </SelectContent>
              </Select>
            </FormControl>
          </FormItem>
        );
      }}
    />
  );
};

const LineChart: React.FC<{
  formValues: z.infer<typeof LineChartSchema>;
  data?: object[];
}> = ({ formValues, data }) => {
  const { theme } = useTheme();

  if (!data) {
    return <div>No data</div>;
  }

  const vegaSpec = createVegaSpec("line", data, formValues, theme, 350, 300);

  if (!vegaSpec) {
    return <div>Chart not supported</div>;
  }

  const compiledSpec = compile(vegaSpec).spec;

  return (
    <Chart className="w-full h-full" vegaSpec={compiledSpec} theme={theme} />
  );
};

const Chart: React.FC<{
  className?: string;
  vegaSpec: Spec;
  theme: ResolvedTheme;
}> = ({ className, vegaSpec, theme }) => {
  return (
    <div className={className}>
      <LazyVegaLite
        spec={vegaSpec}
        theme={theme === "dark" ? "dark" : undefined}
      />
    </div>
  );
};
