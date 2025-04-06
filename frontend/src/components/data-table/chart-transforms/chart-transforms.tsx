/* Copyright 2024 Marimo. All rights reserved. */

import React, { useState, useMemo } from "react";
import { Button } from "@/components/ui/button";
import { ChartBarIcon, TableIcon } from "lucide-react";
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
import { useLastFocusedCellId } from "@/core/cells/focus";
import { useAtom } from "jotai";
import { findActiveCellId } from "@/core/cells/ids";
import { capitalize, debounce } from "lodash-es";
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
import { Logger } from "@/utils/Logger";
import { AxisLabelForm, ColumnSelector } from "./form-components";
import { CHART_TYPE_ICON } from "./icons";

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

// todo: change from jsx.element
export const TablePanel: React.FC<TablePanelProps> = ({
  dataTable,
  getDataUrl,
  fieldTypes,
}) => {
  const [tabs, saveTabs] = useAtom(tabsStorageAtom);
  const [tabNum, setTabNum] = useAtom(tabNumberAtom);
  const [selectedTab, setSelectedTab] = useState(DEFAULT_TAB_NAME);

  const lastFocusedCellId = useLastFocusedCellId();
  const activeCellId = findActiveCellId();
  // TODO: This isn't finding the correct cell
  const cellId = activeCellId || lastFocusedCellId;

  const handleAddTab = () => {
    Logger.debug("handleAddTab", { cellId, tabNum });
    if (!cellId) {
      return;
    }
    const tabName =
      tabNum === 0
        ? NEW_TAB_NAME
        : (`${NEW_TAB_NAME} ${tabNum + 1}` as TabName);
    setTabNum(tabNum + 1);
    setSelectedTab(tabName);

    saveTabs([
      ...tabs,
      {
        cellId,
        tabName,
        chartType: NEW_CHART_TYPE,
        config: getDefaults(ChartSchema),
      },
    ]);
  };

  const handleDeleteTab = (tabName: TabName) => {
    Logger.debug("handleDeleteTab", { tabName });
    if (!cellId) {
      return;
    }
    saveTabs(tabs.filter((tab) => tab.tabName !== tabName));
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
    <Tabs value={selectedTab}>
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
            <span
              className="ml-1.5 text-red-400 hover:font-bold"
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
      <div className="flex flex-col gap-3 w-1/4">
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

      <div className="m-auto">{memoizedChart}</div>
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

  const debouncedSave = useMemo(
    () =>
      debounce((values: z.infer<typeof ChartSchema>) => saveChart(values), 300),
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
            {chartType !== ChartType.PIE && (
              <>
                <TabsTrigger value="x-axis">X-Axis</TabsTrigger>
                <TabsTrigger value="y-axis">Y-Axis</TabsTrigger>
              </>
            )}
          </TabsList>
          <TabsContent value="general" className="flex flex-col gap-2">
            <ColumnSelector
              form={form}
              formFieldName="general.xColumn.field"
              formFieldLabel={
                chartType === ChartType.PIE ? "Theta" : "X column"
              }
              columns={fields || []}
            />
            <div className="flex flex-row gap-2">
              <ColumnSelector
                form={form}
                formFieldName="general.yColumn.field"
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
                              {capitalize(DEFAULT_AGGREGATION)}
                            </SelectItem>
                            {AGGREGATION_FNS.map((agg) => (
                              <SelectItem key={agg} value={agg}>
                                {capitalize(agg)}
                              </SelectItem>
                            ))}
                          </SelectGroup>
                        </SelectContent>
                      </Select>
                    </FormControl>
                  </FormItem>
                )}
              />
            </div>
          </TabsContent>
          {chartType !== ChartType.PIE && (
            <>
              <TabsContent value="x-axis">
                <AxisLabelForm
                  form={form}
                  formFieldName="xAxis.label"
                  formFieldLabel="X-axis Label"
                />
              </TabsContent>
              <TabsContent value="y-axis">
                <AxisLabelForm
                  form={form}
                  formFieldName="yAxis.label"
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
  const compiledSpec = compile(vegaSpec).spec;

  return (
    <div className="w-full h-full">
      <LazyVega
        spec={compiledSpec}
        theme={theme === "dark" ? "dark" : undefined}
      />
    </div>
  );
};
