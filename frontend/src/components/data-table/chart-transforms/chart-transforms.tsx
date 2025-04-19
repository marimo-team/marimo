/* Copyright 2024 Marimo. All rights reserved. */

import React, { useState, useMemo, useRef, useEffect } from "react";
import { Button } from "@/components/ui/button";
import {
  ArrowDownWideNarrowIcon,
  ArrowUpWideNarrowIcon,
  ChevronsUpDown,
  Loader2,
  TableIcon,
  XIcon,
} from "lucide-react";
import { Tabs, TabsTrigger, TabsList, TabsContent } from "@/components/ui/tabs";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../../ui/select";
import type { z } from "zod";
import { type Path, useForm, type UseFormReturn } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import {
  ChartSchema,
  SCALE_TYPES,
  type ScaleType,
  SORT_TYPES,
} from "./chart-schemas";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
} from "@/components/ui/form";
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
import {
  BooleanField,
  ColumnSelector,
  InputField,
  NumberField,
  SelectField,
  SliderField,
} from "./form-components";
import {
  CHART_TYPE_ICON,
  inferScaleType,
  SCALE_TYPE_DESCRIPTIONS,
} from "./constants";
import { useDebouncedCallback } from "@/hooks/useDebounce";
import { cn } from "@/utils/cn";
import { inferFieldTypes } from "../columns";
import { LazyChart } from "./lazy-chart";
import type { DataType } from "@/core/kernel/messages";
import { DATA_TYPE_ICON } from "@/components/datasets/icons";

const NEW_TAB_NAME = "Chart" as TabName;
const NEW_CHART_TYPE = "line" as ChartType;
const DEFAULT_TAB_NAME = "table" as TabName;

export interface TablePanelProps {
  dataTable: JSX.Element;
  displayHeader: boolean;
  getDataUrl?: GetDataUrl;
  fieldTypes?: FieldTypesWithExternalType | null;
}

export const TablePanel: React.FC<TablePanelProps> = ({
  dataTable,
  getDataUrl,
  fieldTypes,
  displayHeader,
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

    // If the element is in the light DOM, we can find it directly
    // Otherwise, we need to traverse up through shadow DOM boundaries
    let cellElement = HTMLCellId.findElement(containerRef.current);

    if (!cellElement) {
      const root = containerRef.current.getRootNode();
      let element: Element | null = containerRef.current;

      while (element && element !== root) {
        cellElement = HTMLCellId.findElement(element);
        if (cellElement) {
          break;
        }
        element =
          element.getRootNode() instanceof ShadowRoot
            ? (element.getRootNode() as ShadowRoot).host
            : element.parentElement;
      }
    }

    if (cellElement) {
      setCellId(HTMLCellId.parse(cellElement.id));
    }
  }, [containerRef, displayHeader]);

  if (!displayHeader || (tabs.length === 0 && !displayHeader)) {
    return dataTable;
  }

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
    <Tabs value={selectedTab} ref={containerRef} className="-mt-1">
      <TabsList>
        <TabsTrigger
          className="text-xs"
          value={DEFAULT_TAB_NAME}
          onClick={() => setSelectedTab(DEFAULT_TAB_NAME)}
        >
          <TableIcon className="w-3 h-3 mr-2" />
          Table
        </TabsTrigger>
        {tabs.map((tab, idx) => (
          <TabsTrigger
            key={idx}
            className="text-xs"
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
        <Button
          variant="text"
          size="icon"
          onClick={handleAddTab}
          title="Add chart"
        >
          +
        </Button>
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
              fieldTypes={fieldTypes ?? inferFieldTypes(dataTable.props.data)}
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
  getDataUrl?: GetDataUrl;
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
    if (!getDataUrl) {
      return [];
    }

    const response = await getDataUrl({});
    if (Array.isArray(response.data_url)) {
      return response.data_url;
    }

    const chartData = await vegaLoadData(
      response.data_url,
      response.format === "arrow"
        ? { type: "arrow" }
        : response.format === "json"
          ? { type: "json" }
          : { type: "csv", parse: "auto" },
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
      return (
        <div className="flex items-center justify-center h-full w-full">
          <Loader2 className="w-10 h-10 animate-spin" strokeWidth={1} />
        </div>
      );
    }
    if (error) {
      return (
        <div className="flex items-center justify-center h-full w-full">
          Error: ""
        </div>
      );
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
    <div className="flex flex-row gap-6 p-3 pt-4 h-full rounded-md border overflow-auto">
      <div className="flex flex-col gap-3 w-1/3">
        <Select
          value={chartTypeSelected}
          onValueChange={(value) => {
            setChartTypeSelected(value as ChartType);
            saveChartType(value as ChartType);
          }}
        >
          <div className="flex flex-row gap-2 items-center">
            <span className="text-sm font-semibold">Type</span>
            <SelectTrigger className="flex-1">
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
      <div className="w-2/3">{memoizedChart}</div>
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

interface Field {
  name: string;
  type: DataType;
}

const ChartForm = ({
  form,
  saveChart,
  fieldTypes,
  chartType,
}: ChartFormProps) => {
  const fields: Field[] | undefined = fieldTypes?.map((field) => {
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
        <Tabs defaultValue="data">
          <TabsList className="w-full">
            <TabsTrigger value="data" className="w-1/2">
              Data
            </TabsTrigger>
            <TabsTrigger value="style" className="w-1/2">
              Style
            </TabsTrigger>
            {/* {chartType !== ChartType.PIE && (
              <>
                <TabsTrigger value="x-axis">X-Axis</TabsTrigger>
                <TabsTrigger value="y-axis">Y-Axis</TabsTrigger>
              </>
            )} */}
            {/* <TabsTrigger value="color">Color</TabsTrigger> */}
          </TabsList>

          <TabsContent value="data">
            <HorizontalRule />
            <TabContainer>
              {chartType === ChartType.LINE && (
                <LineChartForm form={form} fields={fields ?? []} />
              )}
              {/* <BooleanField
                form={form}
                name="general.horizontal"
                formFieldLabel="Horizontal chart"
              /> */}
              {/* <ColumnSelector
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
                    formFieldLabel="Group by (color)"
                    columns={fields ?? []}
                    includeNoneOption={true}
                  />
                  <div
                    className={cn(
                      "flex flex-col self-end gap-1 items-end",
                      chartType === ChartType.BAR && "mt-1.5",
                    )}
                  >
                    <BooleanField
                      form={form}
                      name="general.groupByColumn.binned"
                      formFieldLabel="Binned"
                    />
                    <BooleanField
                      form={form}
                      name="general.stacking"
                      formFieldLabel="Stacked"
                    />
                  </div>
                </div>
              )}

              <hr />

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
              /> */}
            </TabContainer>
          </TabsContent>

          <TabsContent value="style">
            <HorizontalRule />
            <TabContainer>
              <span>hi</span>
            </TabContainer>
          </TabsContent>
          {/* {chartType !== ChartType.PIE && (
            <>
              <AxisTabContent axis="x" form={form} />
              <AxisTabContent axis="y" form={form} />
            </>
          )} */}
          {/* <TabsContent value="color">
            <TabContainer>
              <SelectField
                form={form}
                name="color.scheme"
                formFieldLabel="Color scheme"
                defaultValue={DEFAULT_COLOR_SCHEME}
                options={COLOR_SCHEMES.map((scheme) => ({
                  label: capitalize(scheme),
                  value: scheme,
                }))}
              />
              <ColorArrayField
                form={form}
                name="color.range"
                formFieldLabel="Color range"
              />
              <p className="text-xs">
                <InfoIcon className="w-2.5 h-2.5 inline mb-1 mr-1" />
                If you are using color range, color scheme will be ignored.
              </p>
            </TabContainer>
          </TabsContent> */}
        </Tabs>
      </form>
    </Form>
  );
};

const HorizontalRule: React.FC = () => {
  return <hr className="my-3" />;
};

interface AxisTabContentProps {
  axis: "x" | "y";
  form: UseFormReturn<z.infer<typeof ChartSchema>>;
}

const AxisTabContent: React.FC<AxisTabContentProps> = ({ axis, form }) => {
  const axisName = axis === "x" ? "X" : "Y";

  return (
    <TabsContent value={`${axis}-axis`}>
      <TabContainer className="gap-1">
        <InputField
          form={form}
          name={`${axis}Axis.label`}
          formFieldLabel={`${axisName}-axis Label`}
        />
        <SliderField
          form={form}
          name={`${axis}Axis.width`}
          formFieldLabel={axis === "x" ? "Width" : "Height"}
          value={axis === "x" ? 400 : 300}
          start={axis === "x" ? 200 : 150}
          stop={axis === "x" ? 800 : 600}
        />
        <div className="flex flex-row gap-2 w-full">
          <BooleanField
            form={form}
            name={`${axis}Axis.bin.binned`}
            formFieldLabel="Binned"
          />
          <NumberField
            form={form}
            name={`${axis}Axis.bin.step`}
            formFieldLabel="Bin step"
            step={0.05}
            className="w-32"
          />
        </div>
      </TabContainer>
    </TabsContent>
  );
};

const Chart: React.FC<{
  chartType: ChartType;
  formValues: z.infer<typeof ChartSchema>;
  data?: object[];
}> = ({ chartType, formValues, data }) => {
  return (
    <LazyChart
      chartType={chartType}
      formValues={formValues}
      data={data}
      width="container"
      height={300}
    />
  );
};

const TabContainer: React.FC<{
  className?: string;
  children: React.ReactNode;
}> = ({ children, className }) => {
  return <div className={cn("flex flex-col gap-2", className)}>{children}</div>;
};

const LineChartForm: React.FC<{
  form: UseFormReturn<z.infer<typeof ChartSchema>>;
  fields: Field[];
}> = ({ form, fields }) => {
  const formValues = form.getValues();

  const [xColumn, setXColumn] = useState(formValues.general?.xColumn);
  // TODO: How/when do we choose between a saved scale type and an inferred scale type?
  // For now, we'll use the inferred scale type
  const inferredScaleType = xColumn?.type
    ? inferScaleType(xColumn.type)
    : "string";

  return (
    <>
      <span className="font-semibold my-0">X-Axis</span>
      <ColumnSelector
        form={form}
        name="general.xColumn.field"
        columns={fields}
        onValueChange={(fieldName, type) => {
          setXColumn({ field: fieldName, type });
        }}
      />
      {xColumn && (
        <ScaleTypeSelect
          form={form}
          formFieldLabel="Scale Type"
          name="general.xColumn.scaleType"
          options={SCALE_TYPES.map((type) => {
            const Icon = DATA_TYPE_ICON[type];
            return {
              display: (
                <div className="flex items-center">
                  <Icon className="w-3 h-3 mr-2" />
                  {capitalize(type)}
                </div>
              ),
              value: type,
            };
          })}
          defaultValue={inferredScaleType}
        />
      )}
      {xColumn && (
        <SelectField
          form={form}
          name="general.xColumn.sort"
          formFieldLabel="Sort"
          options={SORT_TYPES.map((type) => ({
            display: (
              <div className="flex items-center">
                {type === "ascending" ? (
                  <ArrowUpWideNarrowIcon className="w-3 h-3 mr-2" />
                ) : type === "descending" ? (
                  <ArrowDownWideNarrowIcon className="w-3 h-3 mr-2" />
                ) : (
                  <ChevronsUpDown className="w-3 h-3 mr-2" />
                )}
                {capitalize(type)}
              </div>
            ),
            value: type,
          }))}
          defaultValue={formValues.general?.xColumn?.sort ?? "none"}
        />
      )}
      <span className="font-semibold my-0">Y-Axis</span>
      <ColumnSelector
        form={form}
        name="general.yColumn.field"
        columns={fields}
      />
    </>
  );
};

const ScaleTypeSelect = <T extends object>({
  form,
  name,
  formFieldLabel,
  options,
  defaultValue,
}: {
  form: UseFormReturn<T>;
  name: Path<T>;
  formFieldLabel: string;
  options: Array<{ display: React.ReactNode; value: string }>;
  defaultValue: string;
}) => {
  const [isOpen, setIsOpen] = React.useState(false);

  return (
    <FormField
      control={form.control}
      name={name}
      render={({ field }) => (
        <FormItem className="flex flex-row items-center gap-2 w-full">
          <FormLabel>{formFieldLabel}</FormLabel>
          <FormControl>
            <Select
              {...field}
              onValueChange={field.onChange}
              value={field.value ?? defaultValue}
              open={isOpen}
              onOpenChange={setIsOpen}
            >
              <SelectTrigger>
                <SelectValue placeholder="Select an option" />
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  {options.map((option) => {
                    const scaleType = option.value;
                    return scaleType === "" ? null : (
                      <SelectItem
                        key={option.value}
                        value={option.value}
                        className="flex flex-col items-start justify-center"
                        subtitle={
                          isOpen && (
                            <span className="text-xs text-muted-foreground">
                              {SCALE_TYPE_DESCRIPTIONS[scaleType as ScaleType]}
                            </span>
                          )
                        }
                      >
                        {option.display}
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
  );
};
