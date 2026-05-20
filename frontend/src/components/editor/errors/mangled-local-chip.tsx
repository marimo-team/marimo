/* Copyright 2026 Marimo. All rights reserved. */
import { EyeOffIcon } from "lucide-react";
import type { JSX } from "react";
import { Tooltip } from "@/components/ui/tooltip";
import type { MangledSegment, UnmangledLocal } from "@/utils/local-variables";
import { CellLinkError } from "../links/cell-link";

interface Props {
  local: UnmangledLocal;
}

/**
 * Renders a compiler-mangled cell-local variable as the user's original name
 * (e.g. `_a`) with an eye-off icon and a tooltip linking to the defining
 * cell.
 */
export const MangledLocalChip = ({ local }: Props): JSX.Element => {
  const tooltipContent = (
    <div className="max-w-xs">
      Local variable <span className="font-code">{local.name}</span> in cell{" "}
      <CellLinkError cellId={local.cellId} />.
    </div>
  );

  return (
    <Tooltip content={tooltipContent}>
      <span className="inline-flex items-center gap-0.5 cursor-help">
        <span className="font-code">{local.name}</span>
        <EyeOffIcon className="h-3 w-3" aria-label="cell-local variable" />
      </span>
    </Tooltip>
  );
};

/**
 * Render an array of `splitMangledLocals` segments as alternating text and
 * `<MangledLocalChip>` nodes. The `keyPrefix` keeps React keys unique when
 * multiple lists coexist on the page.
 */
export function renderMangledSegments(
  segments: MangledSegment[],
  keyPrefix: string,
): JSX.Element[] {
  return segments.map((segment, idx) => {
    const key = `${keyPrefix}-${idx}`;
    if (typeof segment === "string") {
      return <span key={key}>{segment}</span>;
    }
    return <MangledLocalChip key={key} local={segment} />;
  });
}
