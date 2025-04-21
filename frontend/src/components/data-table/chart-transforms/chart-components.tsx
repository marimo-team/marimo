/* Copyright 2024 Marimo. All rights reserved. */

import type { LucideProps } from "lucide-react";
import type { UseFormReturn } from "react-hook-form";
import type { ChartSchema } from "./chart-schemas";
import { type Field, TooltipSelect } from "./form-components";
import type { z } from "zod";
import { cn } from "@/utils/cn";

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

export const TooltipForm: React.FC<{
  form: UseFormReturn<z.infer<typeof ChartSchema>>;
  fields: Field[];
  saveForm: () => void;
}> = ({ form, fields, saveForm }) => {
  return (
    <>
      <Title text="Tooltips" />
      <TooltipSelect
        form={form}
        name="general.tooltips"
        fields={fields}
        saveFunction={saveForm}
      />
    </>
  );
};

export const TabContainer: React.FC<{
  className?: string;
  children: React.ReactNode;
}> = ({ children, className }) => {
  return <div className={cn("flex flex-col gap-2", className)}>{children}</div>;
};
