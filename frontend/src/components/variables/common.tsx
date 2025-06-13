/* Copyright 2024 Marimo. All rights reserved. */
import React from "react";
import { copyToClipboard } from "@/utils/copy";
import { Badge } from "../ui/badge";
import { toast } from "../ui/use-toast";

interface Props extends React.HTMLAttributes<HTMLDivElement> {
  name: string;
  declaredBy: string[];
}

export const VariableName: React.FC<Props> = ({
  name,
  declaredBy,
  onClick,
  ...rest
}) => {
  return (
    <div className="max-w-[130px]" {...rest}>
      <Badge
        title={name}
        variant={declaredBy.length > 1 ? "destructive" : "outline"}
        className="rounded-sm text-ellipsis block overflow-hidden max-w-fit cursor-pointer font-medium"
        onClick={async (evt) => {
          if (onClick) {
            onClick(evt);
            return;
          }
          await copyToClipboard(name);
          toast({ title: "Copied to clipboard" });
        }}
      >
        {name}
      </Badge>
    </div>
  );
};
