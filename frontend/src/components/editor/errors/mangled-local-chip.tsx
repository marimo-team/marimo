/* Copyright 2026 Marimo. All rights reserved. */
import type { JSX } from "react";
import { Tooltip } from "@/components/ui/tooltip";
import type { MangledSegment, UnmangledLocal } from "@/utils/local-variables";
import { CellLinkError } from "../links/cell-link";

interface Props {
  local: UnmangledLocal;
}

/**
 * Renders a compiler-mangled cell-local variable as the user's original name
 * (e.g. `_a`) with a tooltip linking to the defining cell.
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
      <span className="font-code cursor-help">{local.name}</span>
    </Tooltip>
  );
};

interface MangledSegmentsProps {
  segments: MangledSegment[];
}

/**
 * Render an array of `splitMangledLocals` segments as alternating text and
 * `<MangledLocalChip>` nodes.
 */
export const MangledSegments = ({
  segments,
}: MangledSegmentsProps): JSX.Element => (
  <>
    {segments.map((segment, idx) =>
      typeof segment === "string" ? (
        <span key={idx}>{segment}</span>
      ) : (
        <MangledLocalChip key={idx} local={segment} />
      ),
    )}
  </>
);
