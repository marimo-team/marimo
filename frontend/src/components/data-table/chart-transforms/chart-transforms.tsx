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
import "../tables.css";
import type { z } from "zod";
import { useForm } from "react-hook-form";
import { getDefaults } from "@/components/forms/form-utils";
import { zodResolver } from "@hookform/resolvers/zod";
import { LineChartSchema } from "./chart-schemas";
import {
  Form,
  FormControl,
  FormLabel,
  FormField,
  FormItem,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";

interface AdditionalTab {
  name: string;
  value: string;
  component: JSX.Element;
}

// todo: change from jsx.element
export const TablePanel: React.FC<{ dataTable: JSX.Element }> = ({
  dataTable,
}) => {
  const [additionalTabs, setAdditionalTabs] = useState<AdditionalTab[]>([]);

  const handleAddChart = () => {
    setAdditionalTabs([
      ...additionalTabs,
      {
        name: "Chart",
        value: "chart",
        component: <ChartPanel />,
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

export const ChartPanel = () => {
  const form = useForm<z.infer<typeof LineChartSchema>>({
    defaultValues: getDefaults(LineChartSchema),
    resolver: zodResolver(LineChartSchema),
  });

  // use this to track which chart and subsequently form is selected
  const [chartSelected, setChartSelected] = useState({
    chartName: "line",
    form: form,
  });

  return (
    <div className="flex flex-row gap-6 p-3 table-container h-full">
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
          <form onSubmit={(e) => e.preventDefault()}>
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
                        <Input value={field.value} onChange={field.onChange} />
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
                        <Input value={field.value} onChange={field.onChange} />
                      </FormControl>
                    </FormItem>
                  )}
                />
              </TabsContent>
            </Tabs>
          </form>
        </Form>
      </div>

      <div className="m-auto">
        <img
          src="https://www.google.com/images/branding/googlelogo/1x/googlelogo_color_272x92dp.png"
          alt="google logo"
        />
      </div>
    </div>
  );
};

// <DataExplorerComponent
// data="https://raw.githubusercontent.com/kirenz/datasets/b8f17b8fc4907748b3317554d65ffd780edcc057/gapminder.csv"
// value={value}
// setValue={(v) => {
//   setValue(v);
// }}
// />
