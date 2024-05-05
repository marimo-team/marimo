/* Copyright 2024 Marimo. All rights reserved. */
import React from "react";
import { toast } from "../ui/use-toast";
import { Badge } from "../ui/badge";

interface Props {
  name: string;
  declaredBy: string[];
}

export const VariableName: React.FC<Props> = ({ name, declaredBy }) => {
  return (
    <div className="max-w-[130px]">
      <Badge
        title={name}
        variant={declaredBy.length > 1 ? "destructive" : "outline"}
        className="rounded-sm text-ellipsis block overflow-hidden max-w-fit cursor-pointer font-medium"
        onClick={() => {
          navigator.clipboard.writeText(name);
          toast({ title: "Copied to clipboard" });
        }}
      >
        {name}
      </Badge>
    </div>
  );
};
