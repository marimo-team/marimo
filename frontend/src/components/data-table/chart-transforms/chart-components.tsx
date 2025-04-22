/* Copyright 2024 Marimo. All rights reserved. */

import type { LucideProps } from "lucide-react";
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

export const TabContainer: React.FC<{
  className?: string;
  children: React.ReactNode;
}> = ({ children, className }) => {
  return <div className={cn("flex flex-col gap-2", className)}>{children}</div>;
};
