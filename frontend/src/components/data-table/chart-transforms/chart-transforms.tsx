/* Copyright 2024 Marimo. All rights reserved. */

import React, { useState, useMemo, useRef, useEffect } from "react";
import { Button } from "@/components/ui/button";
import {
  ChartBarIcon,
  SquareFunctionIcon,
  TableIcon,
  XIcon,
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
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from "../../ui/select";
import type { z } from "zod";
import { useForm, type UseFormReturn } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { ChartSchema } from "./chart-schemas";
import { Form, FormControl, FormField, FormItem } from "@/components/ui/form";
import { getDefaults } from "@/components/forms/form-utils";
import { useAtom } from "jotai";
import { type CellId, HTMLCellId } from "@/core/cells/ids";
import { capitalize } from "lodash-es";
import {
  type TabName,
  tabsStorageAtom,
  ChartType,
  tabNumberAtom,
  CHART_TYPES,
} from "./storage";
import type { FieldTypesWithExternalType } from "../types";
import { useAsyncData } from "@/hooks/useAsyncData";
import { vegaLoadData } from "@/plugins/impl/vega/loader";
import type { GetDataUrl } from "@/plugins/impl/DataTablePlugin";
import { createVegaSpec, DEFAULT_AGGREGATION } from "./chart-spec";
import { useTheme } from "@/theme/useTheme";
import { compile } from "vega-lite";
import { AGGREGATION_FNS } from "@/plugins/impl/data-frames/types";
import { BooleanField, ColumnSelector, InputField } from "./form-components";
import { AGGREGATION_TYPE_ICON, CHART_TYPE_ICON } from "./icons";
import { Multiselect } from "@/plugins/impl/MultiselectPlugin";
import { useDebouncedCallback } from "@/hooks/useDebounce";

const LazyVega = React.lazy(() =>
  import("react-vega").then((m) => ({ default: m.Vega })),
);

const NEW_TAB_NAME = "Chart" as TabName;
const NEW_CHART_TYPE = "line" as ChartType;
const DEFAULT_TAB_NAME = "table" as TabName;

export interface TablePanelProps {
  dataTable: JSX.Element;
  getDataUrl: GetDataUrl;
  fieldTypes?: FieldTypesWithExternalType | null;
}

export const TablePanel: React.FC<TablePanelProps> = ({
  dataTable,
  getDataUrl,
  fieldTypes,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [cellId, setCellId] = useState<CellId | null>(null);

  const [tabsMap, saveTabsMap] = useAtom(tabsStorageAtom);
  const tabs = cellId ? (tabsMap.get(cellId) ?? []) : [];

  const [tabNum, setTabNum] = useAtom(tabNumberAtom);
  const [selectedTab, setSelectedTab] = useState(DEFAULT_TAB_NAME);

  // Finds cellId in shadow / light DOM
  useEffect(() => {
    if (!containerRef.current) {
      return;
    }
    const root = containerRef.current.getRootNode();
    let element: Element | null = containerRef.current;
    while (element && element !== root) {
      if (element.id?.startsWith("cell-")) {
        setCellId(HTMLCellId.parse(element.id as `cell-${CellId}`));
        break;
      }
      element =
        element.getRootNode() instanceof ShadowRoot
          ? (element.getRootNode() as ShadowRoot).host
          : element.parentElement;
    }
  }, [containerRef]);

  const handleAddTab = () => {
    if (!cellId) {
      return;
    }
    const tabName =
      tabNum === 0
        ? NEW_TAB_NAME
        : (`${NEW_TAB_NAME} ${tabNum + 1}` as TabName);

    const newTabs = new Map(tabsMap);
    newTabs.set(cellId, [
      ...tabs,
      {
        tabName,
        chartType: NEW_CHART_TYPE,
        config: getDefaults(ChartSchema),
      },
    ]);

    saveTabsMap(newTabs);
    setTabNum(tabNum + 1);
    setSelectedTab(tabName);
  };

  const handleDeleteTab = (tabName: TabName) => {
    if (!cellId) {
      return;
    }
    const newTabs = new Map(tabsMap);
    newTabs.set(
      cellId,
      tabs.filter((tab) => tab.tabName !== tabName),
    );
    saveTabsMap(newTabs);
    setSelectedTab(DEFAULT_TAB_NAME);
  };

  const saveTabChart = (
    tabName: TabName,
    chartType: ChartType,
    chartConfig: z.infer<typeof ChartSchema>,
  ) => {
    if (!cellId) {
      return;
    }

    const updatedTabs = new Map(tabsMap);
    updatedTabs.set(
      cellId,
      tabs.map((tab) =>
        tab.tabName === tabName
          ? { ...tab, chartType, config: chartConfig }
          : tab,
      ),
    );
    saveTabsMap(updatedTabs);
  };

  const saveTabChartType = (tabName: TabName, chartType: ChartType) => {
    if (!cellId) {
      return;
    }
    const newTabs = new Map(tabsMap);
    newTabs.set(
      cellId,
      tabs.map((tab) =>
        tab.tabName === tabName ? { ...tab, chartType } : tab,
      ),
    );
    saveTabsMap(newTabs);
  };

  return (
    <Tabs value={selectedTab} ref={containerRef}>
      <TabsList>
        <TabsTrigger
          className="text-xs py-1"
          value={DEFAULT_TAB_NAME}
          onClick={() => setSelectedTab(DEFAULT_TAB_NAME)}
        >
          <TableIcon className="w-3 h-3 mr-2" />
          Table
        </TabsTrigger>
        {tabs.map((tab, idx) => (
          <TabsTrigger
            key={idx}
            className="text-xs py-1"
            value={tab.tabName}
            onClick={() => setSelectedTab(tab.tabName)}
          >
            {tab.tabName}
            <XIcon
              className="w-3 h-3 ml-1 mt-[0.5px] hover:text-red-500 hover:font-semibold"
              onClick={(e) => {
                e.stopPropagation();
                handleDeleteTab(tab.tabName);
              }}
            />
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

      <TabsContent className="mt-1 overflow-hidden" value={DEFAULT_TAB_NAME}>
        {dataTable}
      </TabsContent>
      {tabs.map((tab, idx) => {
        const saveChart = (formValues: z.infer<typeof ChartSchema>) => {
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
  chartConfig: z.infer<typeof ChartSchema> | null;
  chartType: ChartType;
  saveChart: (formValues: z.infer<typeof ChartSchema>) => void;
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
  const form = useForm<z.infer<typeof ChartSchema>>({
    defaultValues: chartConfig ?? getDefaults(ChartSchema),
    resolver: zodResolver(ChartSchema),
  });

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

  // Prevent unnecessary re-renders of the chart
  const memoizedChart = useMemo(() => {
    if (loading) {
      return <div>Loading...</div>;
    }
    if (error) {
      return <div>Error: {error.message}</div>;
    }
    return (
      <Chart
        chartType={chartTypeSelected}
        formValues={memoizedFormValues}
        data={data}
      />
    );
  }, [loading, error, memoizedFormValues, data, chartTypeSelected]);

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
              {CHART_TYPES.map((chartType) => (
                <ChartSelectItem key={chartType} chartType={chartType} />
              ))}
            </SelectContent>
          </div>
        </Select>

        <ChartForm
          form={form}
          saveChart={saveChart}
          fieldTypes={fieldTypes}
          chartType={chartTypeSelected}
        />
      </div>
      {memoizedChart}
    </div>
  );
};

const ChartSelectItem: React.FC<{ chartType: ChartType }> = ({ chartType }) => {
  const Icon = CHART_TYPE_ICON[chartType];
  return (
    <SelectItem value={chartType} className="gap-2">
      <div className="flex items-center">
        <Icon className="w-4 h-4 mr-2" />
        {capitalize(chartType)}
      </div>
    </SelectItem>
  );
};

interface ChartFormProps {
  form: UseFormReturn<z.infer<typeof ChartSchema>>;
  chartType: ChartType;
  saveChart: (formValues: z.infer<typeof ChartSchema>) => void;
  fieldTypes?: FieldTypesWithExternalType | null;
}

const ChartForm = ({
  form,
  saveChart,
  fieldTypes,
  chartType,
}: ChartFormProps) => {
  const fields = fieldTypes?.map((field) => {
    return {
      name: field[0],
      type: field[1][0],
    };
  });

  const debouncedSave = useDebouncedCallback(() => {
    const values = form.getValues();
    saveChart(values);
  }, 300);

  return (
    <Form {...form}>
      <form onSubmit={(e) => e.preventDefault()} onChange={debouncedSave}>
        <Tabs defaultValue="general">
          <TabsList>
            <TabsTrigger value="general">General</TabsTrigger>
            {chartType !== ChartType.PIE && (
              <>
                <TabsTrigger value="x-axis">X-Axis</TabsTrigger>
                <TabsTrigger value="y-axis">Y-Axis</TabsTrigger>
              </>
            )}
          </TabsList>
          <TabsContent value="general" className="flex flex-col gap-3">
            <BooleanField
              form={form}
              name="general.horizontal"
              formFieldLabel="Horizontal chart"
            />
            <ColumnSelector
              form={form}
              name="general.xColumn.field"
              formFieldLabel={
                chartType === ChartType.PIE ? "Theta" : "X column"
              }
              columns={fields || []}
            />
            <div className="flex flex-row gap-2">
              <ColumnSelector
                form={form}
                name="general.yColumn.field"
                formFieldLabel={
                  chartType === ChartType.PIE ? "Color" : "Y column"
                }
                columns={fields || []}
              />
              <FormField
                control={form.control}
                name="general.yColumn.agg"
                render={({ field }) => (
                  <FormItem className="self-end w-24">
                    <FormControl>
                      <Select
                        {...field}
                        value={field.value ?? DEFAULT_AGGREGATION}
                        onValueChange={field.onChange}
                      >
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectGroup>
                            <SelectLabel>Aggregation</SelectLabel>
                            <SelectItem value={DEFAULT_AGGREGATION}>
                              <div className="flex items-center">
                                <SquareFunctionIcon className="w-3 h-3 mr-2" />
                                {capitalize(DEFAULT_AGGREGATION)}
                              </div>
                            </SelectItem>
                            {AGGREGATION_FNS.map((agg) => {
                              const Icon = AGGREGATION_TYPE_ICON[agg];
                              return (
                                <SelectItem key={agg} value={agg}>
                                  <div className="flex items-center">
                                    <Icon className="w-3 h-3 mr-2" />
                                    {capitalize(agg)}
                                  </div>
                                </SelectItem>
                              );
                            })}
                          </SelectGroup>
                        </SelectContent>
                      </Select>
                    </FormControl>
                  </FormItem>
                )}
              />
            </div>

            {chartType !== ChartType.PIE && (
              <div className="flex flex-row gap-2">
                <ColumnSelector
                  form={form}
                  name="general.groupByColumn.field"
                  formFieldLabel="Group by"
                  columns={fields ?? []}
                  includeNoneOption={true}
                />
                {chartType === ChartType.BAR && (
                  <BooleanField
                    form={form}
                    name="general.stacking"
                    formFieldLabel="Stacked"
                    className="self-end"
                  />
                )}
              </div>
            )}

            <hr className="my-2" />

            <InputField
              form={form}
              formFieldLabel="Plot title"
              name="general.title"
            />
            <FormField
              control={form.control}
              name="general.tooltips"
              render={({ field }) => (
                <FormItem>
                  <FormControl>
                    <Multiselect
                      options={fields?.map((field) => field.name) ?? []}
                      value={field.value?.map((item) => item.field) ?? []}
                      setValue={(values) => {
                        const selectedValues =
                          typeof values === "function" ? values([]) : values;

                        // find the field types and form objects
                        const tooltipObjects = selectedValues.map(
                          (fieldName) => {
                            const fieldType = fields?.find(
                              (f) => f.name === fieldName,
                            )?.type;

                            return {
                              field: fieldName,
                              type: fieldType ?? "string",
                            };
                          },
                        );

                        field.onChange(tooltipObjects);
                        // Multiselect doesn't trigger onChange, so we need to save the form manually
                        debouncedSave();
                      }}
                      label="Tooltips"
                      fullWidth={false}
                    />
                  </FormControl>
                </FormItem>
              )}
            />
          </TabsContent>
          {chartType !== ChartType.PIE && (
            <>
              <TabsContent value="x-axis">
                <InputField
                  form={form}
                  name="xAxis.label"
                  formFieldLabel="X-axis Label"
                />
              </TabsContent>
              <TabsContent value="y-axis">
                <InputField
                  form={form}
                  name="yAxis.label"
                  formFieldLabel="Y-axis Label"
                />
              </TabsContent>
            </>
          )}
        </Tabs>
      </form>
    </Form>
  );
};

const Chart: React.FC<{
  chartType: ChartType;
  formValues: z.infer<typeof ChartSchema>;
  data?: object[];
}> = ({ chartType, formValues, data }) => {
  const { theme } = useTheme();

  if (!data) {
    return <div>No data</div>;
  }

  const vegaSpec = createVegaSpec(chartType, data, formValues, theme, 350, 300);

  if (!vegaSpec) {
    return <div>This configuration is not supported</div>;
  }

  const compiledSpec = compile(vegaSpec).spec;

  return (
    <div className="h-full m-auto rounded-md">
      <LazyVega
        spec={compiledSpec}
        theme={theme === "dark" ? "dark" : undefined}
      />
    </div>
  );
};
