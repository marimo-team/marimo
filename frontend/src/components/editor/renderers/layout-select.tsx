/* Copyright 2024 Marimo. All rights reserved. */
import type React from "react";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { LayoutType } from "./types";
import {
  SquareIcon,
  Grid3x3Icon,
  ListIcon,
  PresentationIcon,
} from "lucide-react";
import { isWasm } from "@/core/wasm/utils";
import { useLayoutActions, useLayoutState } from "@/core/layout/layout";
import { logNever } from "@/utils/assertNever";
import { getFeatureFlag } from "@/core/config/feature-flag";

export const LayoutSelect: React.FC = () => {
  const { selectedLayout } = useLayoutState();
  const { setLayoutView } = useLayoutActions();
  const layouts: LayoutType[] = ["vertical", "grid", "slides"];

  // Layouts are not supported in WASM mode by default,
  // unless the feature flag is enabled
  if (isWasm() && !getFeatureFlag("wasm_layouts")) {
    return null;
  }

  return (
    <Select
      data-testid="layout-select"
      value={selectedLayout}
      onValueChange={(v) => setLayoutView(v as LayoutType)}
    >
      <SelectTrigger
        className="min-w-[110px] border-border bg-background"
        data-testid="layout-select"
      >
        <SelectValue placeholder="Select a view" />
      </SelectTrigger>
      <SelectContent>
        <SelectGroup>
          <SelectLabel>View as</SelectLabel>
          {layouts.map((layout) => (
            <SelectItem key={layout} value={layout}>
              <div className="flex items-center gap-1.5 leading-5">
                {renderIcon(layout)}
                <span>{displayName(layout)}</span>
              </div>
            </SelectItem>
          ))}
        </SelectGroup>
      </SelectContent>
    </Select>
  );
};

function renderIcon(layoutType: LayoutType) {
  switch (layoutType) {
    case "vertical":
      return <ListIcon className="h-4 w-4" />;
    case "grid":
      return <Grid3x3Icon className="h-4 w-4" />;
    case "slides":
      return <PresentationIcon className="h-4 w-4" />;
    default:
      logNever(layoutType);
      return <SquareIcon className="h-4 w-4" />;
  }
}

function displayName(layoutType: LayoutType) {
  switch (layoutType) {
    case "vertical":
      return "Vertical";
    case "grid":
      return "Grid";
    case "slides":
      return "Slides";
    default:
      logNever(layoutType);
      return "Unknown";
  }
}
