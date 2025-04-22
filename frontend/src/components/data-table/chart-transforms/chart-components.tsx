/* Copyright 2024 Marimo. All rights reserved. */

import type { LucideProps } from "lucide-react";
import { cn } from "@/utils/cn";
import { ChevronDown, Loader2 } from "lucide-react";
import { capitalize } from "lodash-es";
import * as SelectPrimitive from "@radix-ui/react-select";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectValue,
} from "@/components/ui/select";
import { CHART_TYPE_ICON, CHART_TYPES, type ChartType } from "./constants";
import { ErrorBanner } from "@/plugins/impl/common/error-banner";
import { buttonVariants } from "@/components/ui/button";

export const IconWithText: React.FC<{
  Icon: React.ForwardRefExoticComponent<
    Omit<LucideProps, "ref"> & React.RefAttributes<SVGSVGElement>
  >;
  text: string;
}> = ({ Icon, text }) => {
  return (
    <div className="flex items-center">
      <Icon className="w-3 h-3 mr-2" />
      <span>{text}</span>
    </div>
  );
};

export const Title: React.FC<{ text: string }> = ({ text }) => {
  return <span className="font-semibold my-0">{text}</span>;
};

export const TabContainer: React.FC<{
  className?: string;
  children: React.ReactNode;
}> = ({ children, className }) => {
  return <div className={cn("flex flex-col gap-2", className)}>{children}</div>;
};

export const ChartLoadingState: React.FC = () => (
  <div className="flex items-center gap-2 justify-center h-full w-full">
    <Loader2 className="w-10 h-10 animate-spin" strokeWidth={1} />
    <span>Loading chart...</span>
  </div>
);

export const ChartErrorState: React.FC<{ error: Error }> = ({ error }) => (
  <div className="flex items-center justify-center h-full w-full">
    <ErrorBanner error={error} />
  </div>
);

export const ChartTypeSelect: React.FC<{
  value: ChartType;
  onValueChange: (value: ChartType) => void;
}> = ({ value, onValueChange }) => {
  return (
    <Select value={value} onValueChange={onValueChange}>
      <div className="flex flex-row gap-2 items-center">
        <SelectPrimitive.Trigger
          className={buttonVariants({
            variant: "outline",
            className: "user-select-none w-full justify-between px-3",
          })}
        >
          <SelectValue />
          <SelectPrimitive.Icon asChild={true}>
            <ChevronDown className="h-4 w-4 opacity-50" />
          </SelectPrimitive.Icon>
        </SelectPrimitive.Trigger>
        <SelectContent>
          {CHART_TYPES.map((chartType) => (
            <ChartSelectItem key={chartType} chartType={chartType} />
          ))}
        </SelectContent>
      </div>
    </Select>
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
