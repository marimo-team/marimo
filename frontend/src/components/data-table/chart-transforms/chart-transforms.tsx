/* Copyright 2024 Marimo. All rights reserved. */

import React, { useState } from "react";
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
import { useForm } from "react-hook-form";
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
import { useAsyncData } from "@/hooks/useAsyncData";
import type { PlotChart } from "@/plugins/impl/DataTablePlugin";
import type { VegaLiteSpec } from "@/plugins/impl/vega/types";
import { VegaLite } from "react-vega";
import { resolveVegaSpecData } from "@/plugins/impl/vega/resolve-data";
import { ErrorBanner } from "@/plugins/impl/common/error-banner";
import "@/plugins/impl/vega/vega.css";
import { useTheme } from "@/theme/useTheme";

interface AdditionalTab {
  name: string;
  value: string;
  component: JSX.Element;
}

const Chart = ({ spec }: { spec: VegaLiteSpec }) => {
  const { data: resolvedSpec, error } = useAsyncData(async () => {
    return resolveVegaSpecData(spec);
  }, [spec]);

  const theme = useTheme();

  if (error) {
    return <ErrorBanner error={error} />;
  }

  if (!resolvedSpec) {
    return null;
  }

  return (
    <VegaLite
      spec={resolvedSpec}
      width={350}
      theme={theme.theme === "dark" ? "dark" : undefined}
      actions={true}
    />
  );
};

// todo: change from jsx.element
export const TablePanel: React.FC<{
  dataTable: JSX.Element;
  plotChart: PlotChart;
}> = ({ dataTable, plotChart }) => {
  const [additionalTabs, setAdditionalTabs] = useState<AdditionalTab[]>([]);

  const handleAddChart = () => {
    setAdditionalTabs([
      ...additionalTabs,
      {
        name: "Chart",
        value: "chart",
        component: <ChartPanel plotChart={plotChart} />,
      },
    ]);
  };

  return (
    <Tabs defaultValue="table">
      <TabsList>
        <TabsTrigger className="text-xs py-1" value="table">
          <TableIcon className="w-3 h-3 mr-2" />
          Table
        </TabsTrigger>
        {additionalTabs.map((tab, idx) => (
          <TabsTrigger key={idx} className="text-xs py-1" value={tab.value}>
            {tab.name}
          </TabsTrigger>
        ))}
        <DropdownMenu>
          <DropdownMenuTrigger asChild={true}>
            <Button variant="text" size="icon">
              +
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent>
            <DropdownMenuItem onClick={handleAddChart}>
              <ChartBarIcon className="w-3 h-3 mr-2" />
              Add chart
            </DropdownMenuItem>
            {/* <DropdownMenuItem onClick={handleAddTransform} disabled={true}>
              <Code2Icon className="w-3 h-3 mr-2" />
              Add transform
            </DropdownMenuItem> */}
          </DropdownMenuContent>
        </DropdownMenu>
      </TabsList>

      <TabsContent className="mt-1 overflow-hidden" value="table">
        {dataTable}
      </TabsContent>
      {additionalTabs.map((tab, idx) => (
        <TabsContent key={idx} value={tab.value} className="h-[400px] mt-1">
          {tab.component}
        </TabsContent>
      ))}
    </Tabs>
  );
};

export const ChartPanel: React.FC<{
  plotChart: PlotChart;
}> = ({ plotChart }) => {
  const form = useForm<z.infer<typeof LineChartSchema>>({
    defaultValues: {
      general: {
        xColumn: "",
        yColumn: "",
      },
      xAxis: {
        label: "",
      },
      yAxis: {
        label: "",
      },
    },
    resolver: zodResolver(LineChartSchema),
  });

  // use this to track which chart and subsequently form is selected
  const [chartSelected, setChartSelected] = useState({
    chartName: "line",
    form: form,
  });

  const { data, loading, error } = useAsyncData(async () => {
    const vegaSpec = await plotChart({
      chart_type: "line",
      chart_args: {
        x_column: "peaches",
        y_column: "quantity",
        x_axis: chartSelected.form.getValues().xAxis,
        y_axis: chartSelected.form.getValues().yAxis,
      },
    });
    return vegaSpec;
  }, [chartSelected.form.getValues()]);

  let chart = null;
  if (error) {
    chart = <p>Error plotting chart: {error.message}</p>;
  } else if (loading) {
    chart = <p>Loading...</p>;
  } else if (data?.spec) {
    chart = <Chart spec={data.spec} />;
  }

  return (
    <div className="flex flex-row gap-6 p-3 h-full rounded-md border overflow-auto">
      <div className="flex flex-col gap-3">
        <Select
          value={chartSelected.chartName}
          onValueChange={(value) => {
            setChartSelected({ chartName: value, form: form });
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

        <Form {...chartSelected.form}>
          <form
            onSubmit={(e) => e.preventDefault()}
            onChange={() => {
              console.log(chartSelected.form.getValues());
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
                  control={chartSelected.form.control}
                  name="general.xColumn"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>X column</FormLabel>
                      <FormControl>
                        <Select
                          {...field}
                          onValueChange={field.onChange}
                          value={field.value}
                        >
                          <SelectTrigger className="w-40">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="miles">Miles</SelectItem>
                          </SelectContent>
                        </Select>
                      </FormControl>
                    </FormItem>
                  )}
                />

                <FormField
                  control={chartSelected.form.control}
                  name="general.yColumn"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Y column</FormLabel>
                      <FormControl>
                        <Select
                          {...field}
                          onValueChange={field.onChange}
                          value={field.value}
                        >
                          <SelectTrigger className="w-40">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="quantity">Quantity</SelectItem>
                          </SelectContent>
                        </Select>
                      </FormControl>
                    </FormItem>
                  )}
                />
              </TabsContent>
              <TabsContent value="x-axis">
                <FormField
                  control={chartSelected.form.control}
                  name="xAxis.label"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>X-axis Label</FormLabel>
                      <FormControl>
                        <DebouncedInput
                          {...field}
                          value={field.value}
                          onValueChange={field.onChange}
                        />
                      </FormControl>
                    </FormItem>
                  )}
                />
              </TabsContent>
              <TabsContent value="y-axis">
                <FormField
                  control={chartSelected.form.control}
                  name="yAxis.label"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Y-axis Label</FormLabel>
                      <FormControl>
                        <DebouncedInput
                          {...field}
                          value={field.value}
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
      </div>

      <div className="m-auto">{chart}</div>
    </div>
  );
};
