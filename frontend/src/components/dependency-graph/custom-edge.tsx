/* Copyright 2026 Marimo. All rights reserved. */

import { memo } from "react";
import { BaseEdge, type EdgeProps, getBezierPath } from "reactflow";
import type { DependencyEdgeData } from "./elements";

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

  return (
    <BaseEdge
      path={path}
      markerEnd={markerEnd}
      style={{
        strokeWidth: isStateFlow ? 2 : 1.5,
        stroke: isStateFlow ? "var(--amber-10)" : "var(--gray-8)",
        strokeDasharray: isStateFlow ? "5 3" : undefined,
      }}
    />
  );
});
DependencyEdge.displayName = "DependencyEdge";

export const edgeTypes = {
  dependency: DependencyEdge,
};
