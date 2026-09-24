/* Copyright 2026 Marimo. All rights reserved. */

import { zodResolver } from "@hookform/resolvers/zod";
import {
  AlertTriangle,
  ChartColumnIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  CodeIcon,
  DatabaseIcon,
  PaintRollerIcon,
} from "lucide-react";
import React, { useMemo, useState } from "react";
import { type UseFormReturn, useForm } from "react-hook-form";
import useResizeObserver from "use-resize-observer";
import { PythonIcon } from "@/components/editor/cell/code/icons";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Form } from "@/components/ui/form";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useAsyncData } from "@/hooks/useAsyncData";
import { useDebouncedCallback } from "@/hooks/useDebounce";
import type { GetDataUrl } from "@/plugins/impl/DataTablePlugin";
import { vegaLoadData } from "@/plugins/impl/vega/loader";
import { useTheme } from "@/theme/useTheme";
import type { FieldTypesWithExternalType } from "../types";
import { generateAltairChartSnippet } from "./chart-spec/altair-generator";
import { createSpecWithoutData } from "./chart-spec/spec";
import { ChartTypeSelect } from "./components/chart-items";
import { ChartErrorState, ChartLoadingState } from "./components/chart-states";
import type { Field } from "./components/form-fields";
import { CodeSnippet, TabContainer } from "./components/layouts";
import { ChartFormContext } from "./context";
import { CommonChartForm, StyleForm } from "./forms/common-chart";
import { HeatmapForm } from "./forms/heatmap";
import { PieForm } from "./forms/pie";
import { LazyChart } from "./lazy-chart";
import { ChartSchema, type ChartSchemaType, getChartDefaults } from "./schemas";
import { ChartType } from "./types";

const CHART_HEIGHT = 290;

const CHART_PLACEHOLDER_CODE = "X and Y columns are not set";

export const ChartPanel: React.FC<{
  tableData: unknown[];
  chartConfig: ChartSchemaType | null;
  chartType: ChartType;
  saveChart: (formValues: ChartSchemaType) => void;
  saveChartType: (chartType: ChartType) => void;
  getDataUrl?: GetDataUrl;
  fieldTypes?: FieldTypesWithExternalType | null;
  isLargeDataset: boolean;
}> = ({
  tableData,
  chartConfig,
  chartType,
  saveChart,
  saveChartType,
  getDataUrl,
  fieldTypes,
  isLargeDataset,
}) => {
  const { theme } = useTheme();
  const form = useForm<ChartSchemaType>({
    defaultValues: chartConfig ?? getChartDefaults(),
    resolver: zodResolver(ChartSchema),
  });

  const [selectedChartType, setSelectedChartType] =
    useState<ChartType>(chartType);
  const [formCollapsed, setFormCollapsed] = useState(false);

  const [renderLargeCharts, setRenderLargeCharts] = useState(!isLargeDataset);

  const { ref: chartContainerRef } = useResizeObserver();

  const { data, isPending, error } = useAsyncData(async () => {
    if (!getDataUrl || tableData.length === 0 || !renderLargeCharts) {
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
    // Re-run when the data table changes
  }, [tableData, renderLargeCharts]);

  const formValues = form.watch();

  // This ensures the chart re-renders when the actual values change
  const memoizedFormValues = useMemo(() => {
    return structuredClone(formValues);
  }, [formValues]);

  const specWithoutData = createSpecWithoutData(
    selectedChartType,
    memoizedFormValues,
    theme,
    "container",
    CHART_HEIGHT,
  );

  // Prevent unnecessary re-renders of the chart
  const memoizedChart = useMemo(() => {
    if (isPending) {
      return <ChartLoadingState />;
    }
    if (error) {
      return <ChartErrorState error={error} />;
    }
    if (!renderLargeCharts) {
      return (
        <Alert
          variant="warning"
          className="flex flex-row gap-2 items-center w-2/3 mx-auto"
        >
          <AlertTriangle className="h-4 w-4 mt-1" />
          <AlertDescription className="flex flex-row justify-between items-center w-full">
            <span>
              Rendering large datasets is not well supported and may crash the
              browser
            </span>
            <Button
              variant="warn"
              onClick={() => setRenderLargeCharts(true)}
              className="h-8"
            >
              Proceed
            </Button>
          </AlertDescription>
        </Alert>
      );
    }
    return (
      <LazyChart baseSpec={specWithoutData} data={data} height={CHART_HEIGHT} />
    );
  }, [isPending, error, renderLargeCharts, specWithoutData, data]);

  const developmentMode = import.meta.env.DEV;

  const renderChartDisplay = () => {
    let altairCodeSnippet = CHART_PLACEHOLDER_CODE;
    if (typeof specWithoutData !== "string") {
      altairCodeSnippet = generateAltairChartSnippet(
        specWithoutData,
        "_df",
        "_chart",
      );
    }

    return (
      <Tabs defaultValue="chart">
        <div className="flex flex-row gap-1.5 items-center">
          <TabsList>
            <TabsTrigger value="chart" className="h-6">
              <ChartColumnIcon className="text-muted-foreground mr-2 w-4 h-4" />
              Chart
            </TabsTrigger>
            <TabsTrigger value="code" className="h-6">
              <PythonIcon className="text-muted-foreground mr-2" />
              Python code
            </TabsTrigger>
            {developmentMode && (
              <>
                <TabsTrigger value="formValues" className="h-6">
                  <CodeIcon className="text-muted-foreground mr-2 w-4 h-4" />
                  Form values (debug)
                </TabsTrigger>
                <TabsTrigger value="vegaSpec" className="h-6">
                  <CodeIcon className="text-muted-foreground mr-2 w-4 h-4" />
                  Vega spec (debug)
                </TabsTrigger>
              </>
            )}
          </TabsList>
        </div>

        <TabsContent value="chart" ref={chartContainerRef}>
          {memoizedChart}
        </TabsContent>
        <TabsContent value="code">
          <CodeSnippet
            code={altairCodeSnippet}
            insertNewCell={altairCodeSnippet !== CHART_PLACEHOLDER_CODE}
            language="python"
          />
        </TabsContent>
        {developmentMode && (
          <>
            <TabsContent value="formValues">
              <CodeSnippet
                code={JSON.stringify(formValues, null, 2)}
                language="python"
              />
            </TabsContent>
            <TabsContent value="vegaSpec">
              <CodeSnippet
                code={JSON.stringify(specWithoutData, null, 2)}
                language="python"
              />
            </TabsContent>
          </>
        )}
      </Tabs>
    );
  };

  const chartForm = (
    <>
      <ChartTypeSelect
        value={selectedChartType}
        onValueChange={(value) => {
          setSelectedChartType(value);
          saveChartType(value);
        }}
      />

      <ChartFormContainer
        form={form}
        saveChart={saveChart}
        fieldTypes={fieldTypes}
        chartType={selectedChartType}
      />
    </>
  );

  return (
    <div className="flex flex-row gap-2 h-full rounded-md border-t pr-2">
      <div
        className={`relative flex flex-col gap-2 overflow-auto px-2 py-3 scrollbar-thin transition-width duration-200 ${formCollapsed ? "w-8" : "w-[300px]"}`}
      >
        {!formCollapsed && chartForm}
        <Button
          variant="outline"
          size="icon"
          className="border-border ml-auto"
          onClick={() => setFormCollapsed((prev) => !prev)}
          title={formCollapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {formCollapsed ? (
            <ChevronRightIcon className="w-4 h-5" />
          ) : (
            <ChevronLeftIcon className="w-4 h-5" />
          )}
        </Button>
      </div>
      <div className="flex-1 overflow-auto h-full w-full mt-3">
        {renderChartDisplay()}
      </div>
    </div>
  );
};

const ChartFormContainer = ({
  form,
  saveChart,
  fieldTypes,
  chartType,
}: {
  form: UseFormReturn<ChartSchemaType>;
  chartType: ChartType;
  saveChart: (formValues: ChartSchemaType) => void;
  fieldTypes?: FieldTypesWithExternalType | null;
}) => {
  let fields: Field[] = [];
  if (fieldTypes) {
    fields = fieldTypes.map((field) => {
      return {
        name: field[0],
        type: field[1][0],
      };
    });
  }

  const debouncedSave = useDebouncedCallback(() => {
    const values = form.getValues();
    saveChart(values);
  }, 300);

  let ChartForm = CommonChartForm;

  if (chartType === ChartType.PIE) {
    ChartForm = PieForm;
  } else if (chartType === ChartType.HEATMAP) {
    ChartForm = HeatmapForm;
  }

  return (
    <ChartFormContext value={{ fields, saveForm: debouncedSave, chartType }}>
      <Form {...form}>
        <form onSubmit={(e) => e.preventDefault()} onChange={debouncedSave}>
          <Tabs defaultValue="data">
            <TabsList className="w-full">
              <TabsTrigger value="data" className="w-1/2 h-6">
                <DatabaseIcon className="w-4 h-4 mr-2" />
                Data
              </TabsTrigger>
              <TabsTrigger value="style" className="w-1/2 h-6">
                <PaintRollerIcon className="w-4 h-4 mr-2" />
                Style
              </TabsTrigger>
            </TabsList>

            <TabsContent value="data">
              <hr className="my-2" />
              <TabContainer>
                <ChartForm />
              </TabContainer>
            </TabsContent>

            <TabsContent value="style">
              <hr className="my-2" />
              <TabContainer>
                <StyleForm />
              </TabContainer>
            </TabsContent>
          </Tabs>
        </form>
      </Form>
    </ChartFormContext>
  );
};
