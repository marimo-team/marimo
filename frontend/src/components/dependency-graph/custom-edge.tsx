/* Copyright 2026 Marimo. All rights reserved. */

import { memo } from "react";
import { BaseEdge, type EdgeProps, getBezierPath } from "reactflow";
import {
  DEFAULT_EDGE_COLOR,
  type DependencyEdgeData,
  STATE_FLOW_EDGE_COLOR,
} from "./elements";

// Gentle curvature keeps edges reading as clean directional splines
// (TensorBoard-style) rather than hard right-angle elbows.
const EDGE_CURVATURE = 0.35;

/**
 * A dependency edge, drawn as a smooth curved spline that flows out of the
 * source handle and into the target — the TensorBoard graph aesthetic. Mutable
 * `State`/setter flows get a distinct dashed accent style.
 */
export const DependencyEdge = memo((props: EdgeProps<DependencyEdgeData>) => {
  const {
    sourceX,
    sourceY,
    targetX,
    targetY,
    sourcePosition,
    targetPosition,
    markerEnd,
    data,
    selected,
  } = props;

  const [path] = getBezierPath({
    sourceX,
    sourceY,
    targetX,
    targetY,
    sourcePosition,
    targetPosition,
    curvature: EDGE_CURVATURE,
  });

  const isStateFlow = data?.isStateFlow ?? false;
  // The inline stroke replaces React Flow's stylesheet-driven edge colors, so
  // the selected state must be restyled here too or it becomes invisible.
  const stroke = selected
    ? "var(--primary)"
    : isStateFlow
      ? STATE_FLOW_EDGE_COLOR
      : DEFAULT_EDGE_COLOR;

  return (
    <BaseEdge
      path={path}
      markerEnd={markerEnd}
      style={{
        strokeWidth: selected ? 2.5 : isStateFlow ? 2 : 1.5,
        stroke,
        strokeDasharray: isStateFlow ? "5 3" : undefined,
      }}
    />
  );
});
DependencyEdge.displayName = "DependencyEdge";

export const edgeTypes = {
  dependency: DependencyEdge,
};
