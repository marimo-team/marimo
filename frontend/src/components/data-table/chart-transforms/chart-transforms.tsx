/* Copyright 2024 Marimo. All rights reserved. */

import React, { useState, useMemo, useRef, useEffect } from "react";
import { Button } from "@/components/ui/button";
import {
  TableIcon,
  XIcon,
  InfoIcon,
  ArrowUpWideNarrowIcon,
  ArrowDownWideNarrowIcon,
} from "lucide-react";
import { Tabs, TabsTrigger, TabsList, TabsContent } from "@/components/ui/tabs";
import type { z } from "zod";
import { useForm, type UseFormReturn } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import {
  ChartSchema,
  DEFAULT_COLOR_SCHEME,
  type SelectableDataType,
  SORT_TYPES,
} from "./chart-schemas";
import { Form } from "@/components/ui/form";
import { getDefaults } from "@/components/forms/form-utils";
import { useAtom } from "jotai";
import { type CellId, HTMLCellId } from "@/core/cells/ids";
import { capitalize } from "lodash-es";
import { type TabName, tabsStorageAtom, tabNumberAtom } from "./storage";
import type { FieldTypesWithExternalType } from "../types";
import { useAsyncData } from "@/hooks/useAsyncData";
import { vegaLoadData } from "@/plugins/impl/vega/loader";
import type { GetDataUrl } from "@/plugins/impl/DataTablePlugin";
import {
  AggregationSelect,
  BooleanField,
  ColorArrayField,
  ColumnSelector,
  type Field,
  InputField,
  NumberField,
  DataTypeSelect,
  SelectField,
  SliderField,
  TimeUnitSelect,
  TooltipSelect,
} from "./form-components";
import { ChartType, COLOR_SCHEMES } from "./constants";
import { useDebouncedCallback } from "@/hooks/useDebounce";
import { inferFieldTypes } from "../columns";
import { LazyChart } from "./lazy-chart";
import { FieldValidators, TypeConverters } from "./chart-spec";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import {
  IconWithText,
  TabContainer,
  Title,
  ChartLoadingState,
  ChartErrorState,
  ChartTypeSelect,
} from "./chart-components";

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

  const [selectedChartType, setSelectedChartType] =
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
      return <ChartLoadingState />;
    }
    if (error) {
      return <ChartErrorState error={error} />;
    }
    return (
      <LazyChart
        chartType={selectedChartType}
        formValues={memoizedFormValues}
        data={data}
        width="container"
        height={300}
      />
    );
  }, [loading, error, memoizedFormValues, data, selectedChartType]);

  return (
    <div className="flex flex-row gap-6 p-3 pt-4 h-full rounded-md border overflow-auto">
      <div className="flex flex-col gap-3 w-1/3">
        <ChartTypeSelect
          value={selectedChartType}
          onValueChange={(value) => {
            setSelectedChartType(value);
            saveChartType(value);
          }}
        />

        <ChartForm
          form={form}
          saveChart={saveChart}
          fieldTypes={fieldTypes}
          chartType={selectedChartType}
        />
      </div>
      <div className="w-2/3">{memoizedChart}</div>
    </div>
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

  const ChartForm =
    chartType === ChartType.PIE ? PieChartForm : CommonChartForm;

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
          </TabsList>

          <TabsContent value="data">
            <hr className="my-3" />
            <TabContainer>
              <ChartForm
                form={form}
                fields={fields ?? []}
                saveForm={debouncedSave}
              />
            </TabContainer>
          </TabsContent>

          <TabsContent value="style">
            <hr className="my-3" />
            <TabContainer>
              <StyleForm
                form={form}
                fields={fields ?? []}
                saveForm={debouncedSave}
              />
            </TabContainer>
          </TabsContent>
        </Tabs>
      </form>
    </Form>
  );
};

const CommonChartForm: React.FC<{
  form: UseFormReturn<z.infer<typeof ChartSchema>>;
  fields: Field[];
  saveForm: () => void;
}> = ({ form, fields, saveForm }) => {
  const formValues = form.getValues();

  const [xColumn, setXColumn] = useState(formValues.general?.xColumn);
  const [yColumn, setYColumn] = useState(formValues.general?.yColumn);
  const [groupByColumn, setGroupByColumn] = useState(
    formValues.general?.colorByColumn,
  );

  const xColumnChosen = FieldValidators.exists(xColumn?.field);

  // TODO: How/when do we choose between a saved scale type and an inferred scale type?
  // For now, we'll use the inferred scale type
  const inferredDataType = xColumn?.type
    ? TypeConverters.toSelectableDataType(xColumn.type)
    : "string";

  const inferredGroupByDataType = groupByColumn?.type
    ? TypeConverters.toSelectableDataType(groupByColumn.type)
    : "string";

  return (
    <>
      <Title text="X-Axis" />
      <ColumnSelector
        form={form}
        name="general.xColumn.field"
        columns={fields}
        onValueChange={(fieldName, type) => {
          setXColumn({ field: fieldName, type });
        }}
      />
      {xColumnChosen && (
        <DataTypeSelect
          form={form}
          formFieldLabel="Data Type"
          name="general.xColumn.selectedDataType"
          defaultValue={inferredDataType}
          onValueChange={(value) => {
            setXColumn({
              ...xColumn,
              selectedDataType: value as SelectableDataType,
            });
          }}
        />
      )}
      {xColumn?.selectedDataType === "temporal" && (
        <TimeUnitSelect
          form={form}
          name="general.xColumn.timeUnit"
          formFieldLabel="Time Resolution"
        />
      )}
      {xColumnChosen && (
        <SelectField
          form={form}
          name="general.xColumn.sort"
          formFieldLabel="Sort"
          options={SORT_TYPES.map((type) => ({
            display: (
              <IconWithText
                Icon={
                  type === "ascending"
                    ? ArrowUpWideNarrowIcon
                    : ArrowDownWideNarrowIcon
                }
                text={capitalize(type)}
              />
            ),
            value: type,
          }))}
          defaultValue={formValues.general?.xColumn?.sort ?? "ascending"}
        />
      )}
      <Title text="Y-Axis" />
      <div className="flex flex-row gap-2">
        <ColumnSelector
          form={form}
          name="general.yColumn.field"
          columns={fields}
          onValueChange={(fieldName, type) => {
            setYColumn({ field: fieldName, type });
          }}
        />
        <AggregationSelect form={form} name="general.yColumn.agg" />
      </div>
      {FieldValidators.exists(yColumn?.field) && (
        <>
          <DataTypeSelect
            form={form}
            formFieldLabel="Data Type"
            name="general.yColumn.selectedDataType"
            defaultValue={inferredDataType}
            onValueChange={(value) => {
              setYColumn({
                ...yColumn,
                selectedDataType: value as SelectableDataType,
              });
            }}
          />
          {yColumn?.selectedDataType === "temporal" && (
            <TimeUnitSelect
              form={form}
              name="general.yColumn.timeUnit"
              formFieldLabel="Time Resolution"
            />
          )}
          <BooleanField
            form={form}
            name="general.horizontal"
            formFieldLabel="Horizontal chart"
          />
        </>
      )}
      {yColumn && (
        <>
          <Title text="Color by" />
          <div className="flex flex-row gap-2">
            <ColumnSelector
              form={form}
              name="general.colorByColumn.field"
              columns={fields}
              onValueChange={(fieldName, type) => {
                setGroupByColumn({ field: fieldName, type });
              }}
            />
            <AggregationSelect form={form} name="general.colorByColumn.agg" />
          </div>
          {FieldValidators.exists(groupByColumn?.field) && (
            <>
              <DataTypeSelect
                form={form}
                name="general.colorByColumn.selectedDataType"
                formFieldLabel="Data Type"
                defaultValue={inferredGroupByDataType}
              />
              <div className="flex flex-row gap-2">
                <BooleanField
                  form={form}
                  name="general.stacking"
                  formFieldLabel="Stacked"
                />
              </div>
            </>
          )}
        </>
      )}

      <hr />
      <Title text="General" />
      <TooltipSelect
        form={form}
        name="general.tooltips"
        fields={fields}
        saveFunction={saveForm}
        formFieldLabel="Tooltips"
      />
    </>
  );
};

const PieChartForm: React.FC<{
  form: UseFormReturn<z.infer<typeof ChartSchema>>;
  fields: Field[];
  saveForm: () => void;
}> = ({ form, fields, saveForm }) => {
  const [colorByColumn, setColorByColumn] = useState(
    form.getValues().general.colorByColumn,
  );

  const inferredColorByDataType = colorByColumn?.type
    ? TypeConverters.toSelectableDataType(colorByColumn.type)
    : "string";

  return (
    <>
      <Title text="Color by" />
      <ColumnSelector
        form={form}
        name="general.colorByColumn.field"
        columns={fields}
        onValueChange={(fieldName, type) => {
          setColorByColumn({ field: fieldName, type });
        }}
      />
      {FieldValidators.exists(colorByColumn?.field) && (
        <DataTypeSelect
          form={form}
          name="general.colorByColumn.selectedDataType"
          formFieldLabel="Data Type"
          defaultValue={inferredColorByDataType}
          onValueChange={(value) => {
            setColorByColumn({
              ...colorByColumn,
              selectedDataType: value as SelectableDataType,
            });
          }}
        />
      )}

      <Title text="Size by" />
      <div className="flex flex-row gap-2">
        <ColumnSelector
          form={form}
          name="general.yColumn.field"
          columns={fields}
        />
        <AggregationSelect form={form} name="general.yColumn.agg" />
      </div>

      <hr />
      <Title text="General" />
      <TooltipSelect
        form={form}
        name="general.tooltips"
        fields={fields}
        saveFunction={saveForm}
        formFieldLabel="Tooltips"
      />
      <NumberField
        form={form}
        name="style.innerRadius"
        formFieldLabel="Donut size"
        className="w-32"
      />
    </>
  );
};

const StyleForm: React.FC<{
  form: UseFormReturn<z.infer<typeof ChartSchema>>;
  fields: Field[];
  saveForm: () => void;
}> = ({ form, fields, saveForm }) => {
  const renderBinFields = (axis: "x" | "y") => {
    return (
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
    );
  };

  return (
    <Accordion type="multiple">
      <AccordionItem value="general" className="border-none">
        <AccordionTrigger className="pt-0 pb-2">
          <Title text="General" />
        </AccordionTrigger>
        <AccordionContent wrapperClassName="pb-2">
          <InputField
            form={form}
            formFieldLabel="Plot title"
            name="general.title"
          />
        </AccordionContent>
      </AccordionItem>

      <AccordionItem value="xAxis" className="border-none">
        <AccordionTrigger className="py-2">
          <Title text="X-Axis" />
        </AccordionTrigger>
        <AccordionContent wrapperClassName="pb-2 flex flex-col gap-2">
          <InputField form={form} formFieldLabel="Label" name="xAxis.label" />
          <SliderField
            form={form}
            name="xAxis.width"
            formFieldLabel="Width"
            value={400}
            start={200}
            stop={800}
          />
          {renderBinFields("x")}
        </AccordionContent>
      </AccordionItem>

      <AccordionItem value="yAxis" className="border-none">
        <AccordionTrigger className="py-2">
          <Title text="Y-Axis" />
        </AccordionTrigger>
        <AccordionContent wrapperClassName="pb-2 flex flex-col gap-2">
          <InputField form={form} formFieldLabel="Label" name="yAxis.label" />
          <SliderField
            form={form}
            name="yAxis.height"
            formFieldLabel="Height"
            value={300}
            start={150}
            stop={600}
          />
          {renderBinFields("y")}
        </AccordionContent>
      </AccordionItem>

      <AccordionItem value="color" className="border-none">
        <AccordionTrigger className="py-2">
          <Title text="Color" />
        </AccordionTrigger>
        <AccordionContent wrapperClassName="pb-2 flex flex-col gap-2">
          <SelectField
            form={form}
            name="color.scheme"
            formFieldLabel="Color scheme"
            defaultValue={DEFAULT_COLOR_SCHEME}
            options={COLOR_SCHEMES.map((scheme) => ({
              display: capitalize(scheme),
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
        </AccordionContent>
      </AccordionItem>
    </Accordion>
  );
};
