/* Copyright 2026 Marimo. All rights reserved. */

import { dequal as isEqual } from "dequal";
import { set } from "lodash-es";
import type * as Plotly from "plotly.js";
import { z } from "zod";
import type { Figure } from "./Plot";

type SceneKey = Extract<keyof Plotly.Layout, "scene" | `scene${number}`>;
type Revision = string | number | boolean;

interface CameraState {
  camera: Partial<Plotly.Camera>;
  revision: Revision;
  initialCamera: Partial<Plotly.Camera> | undefined;
  traceTypes: string[];
}

export type PlotlyCameraState = Partial<Record<SceneKey, CameraState>>;

const point = z
  .object({ x: z.number(), y: z.number(), z: z.number() })
  .partial();
const cameraSchema = z
  .object({ eye: point, center: point, up: point })
  .partial()
  .passthrough();

function isSceneKey(key: string): key is SceneKey {
  return /^scene(?:[2-9]\d*|1\d+)?$/.test(key);
}

// Plotly's gl3d trace types; every other trace lives outside 3D scenes.
const SCENE_TRACE_TYPES = new Set<string>([
  "cone",
  "isosurface",
  "mesh3d",
  "scatter3d",
  "streamtube",
  "surface",
  "volume",
]);

function traceTypes(figure: Figure, scene: SceneKey): string[] {
  return figure.data.flatMap((trace) => {
    const type = trace.type ?? "scatter";
    const destination = "scene" in trace ? (trace.scene ?? "scene") : "scene";
    return SCENE_TRACE_TYPES.has(type) && destination === scene ? [type] : [];
  });
}

function cameraRevision(
  layout: Partial<Plotly.Layout>,
  scene: SceneKey,
): Revision | undefined {
  const sceneLayout = layout[scene];
  // Scene uirevision is supported by Plotly but missing from @types/plotly.js.
  const revision =
    sceneLayout && "uirevision" in sceneLayout
      ? (sceneLayout.uirevision ?? layout.uirevision)
      : layout.uirevision;
  return typeof revision === "string" ||
    typeof revision === "number" ||
    typeof revision === "boolean"
    ? revision
    : undefined;
}

function isCompatible(figure: Figure, scene: SceneKey, state: CameraState) {
  const revision = cameraRevision(figure.layout, scene);
  return (
    Boolean(revision) &&
    revision === state.revision &&
    isEqual(figure.layout[scene]?.camera, state.initialCamera) &&
    isEqual(traceTypes(figure, scene), state.traceTypes)
  );
}

/**
 * Drops saved cameras that no longer match the figure. Plotly compares
 * uirevision with the preceding update only, so a camera saved at revision A
 * must not come back after the figure goes A -> B -> A.
 */
export function pruneCameraState(
  figure: Figure,
  cameras: PlotlyCameraState | undefined,
): PlotlyCameraState | undefined {
  if (!cameras) {
    return cameras;
  }
  const compatible: PlotlyCameraState = {};
  for (const [key, state] of Object.entries(cameras)) {
    if (isSceneKey(key) && state && isCompatible(figure, key, state)) {
      compatible[key] = state;
    }
  }
  return Object.keys(compatible).length === Object.keys(cameras).length
    ? cameras
    : compatible;
}

export function captureCameraState(
  figure: Figure,
  event: Plotly.PlotRelayoutEvent,
  previous: PlotlyCameraState = {},
): PlotlyCameraState | undefined {
  const updates: PlotlyCameraState = {};
  const restoredLayout = restoreCameraLayout(figure, previous);
  for (const [key, value] of Object.entries(event)) {
    const [scene, property, ...path] = key.split(".");
    if (property !== "camera" || !scene || !isSceneKey(scene)) {
      continue;
    }
    if (
      path.length > 0 &&
      !/^(eye|center|up)(\.[xyz])?$|^projection(\.type)?$/.test(path.join("."))
    ) {
      continue;
    }
    const revision = cameraRevision(figure.layout, scene);
    const priorCamera =
      updates[scene]?.camera ??
      restoredLayout[scene]?.camera ??
      figure.layout[scene]?.camera;
    const update =
      path.length > 0
        ? set(structuredClone(priorCamera ?? {}), path, value)
        : value;
    const camera = cameraSchema.safeParse(update);
    if (!revision || !camera.success) {
      continue;
    }
    updates[scene] = {
      camera: structuredClone(camera.data),
      revision,
      initialCamera: structuredClone(figure.layout[scene]?.camera),
      traceTypes: traceTypes(figure, scene),
    };
  }
  return Object.keys(updates).length > 0
    ? { ...previous, ...updates }
    : undefined;
}

export function restoreCameraLayout(
  figure: Figure,
  cameras: PlotlyCameraState = {},
): Partial<Plotly.Layout> {
  const layout: Partial<Plotly.Layout> = {};
  for (const [key, state] of Object.entries(cameras)) {
    if (isSceneKey(key) && state && isCompatible(figure, key, state)) {
      layout[key] = {
        ...structuredClone(figure.layout[key]),
        camera: structuredClone(state.camera),
      };
    }
  }
  return layout;
}
