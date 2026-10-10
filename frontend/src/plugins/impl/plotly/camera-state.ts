/* Copyright 2026 Marimo. All rights reserved. */

import { dequal as isEqual } from "dequal";
import { set } from "lodash-es";
import type * as Plotly from "plotly.js";
import { z } from "zod";
import type { Figure } from "./Plot";

type SceneKey = Extract<keyof Plotly.Layout, "scene" | `scene${number}`>;

interface CameraState {
  camera: Partial<Plotly.Camera>;
  revision: string | number;
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

function traceTypes(figure: Figure): string[] {
  return figure.data.map(
    (trace) =>
      `${trace.type ?? "scatter"}:${"scene" in trace ? (trace.scene ?? "scene") : "scene"}`,
  );
}

function cameraRevision(layout: Partial<Plotly.Layout>, scene: SceneKey) {
  const sceneLayout = layout[scene];
  // Scene uirevision is supported by Plotly but missing from @types/plotly.js.
  const revision =
    sceneLayout && "uirevision" in sceneLayout
      ? (sceneLayout.uirevision ?? layout.uirevision)
      : layout.uirevision;
  return typeof revision === "string" || typeof revision === "number"
    ? revision
    : undefined;
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
      traceTypes: traceTypes(figure),
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
    if (!isSceneKey(key) || !state) {
      continue;
    }
    const scene = figure.layout[key];
    const revision = cameraRevision(figure.layout, key);
    if (
      revision &&
      revision === state.revision &&
      isEqual(scene?.camera, state.initialCamera) &&
      isEqual(traceTypes(figure), state.traceTypes)
    ) {
      layout[key] = {
        ...structuredClone(scene),
        camera: structuredClone(state.camera),
      };
    }
  }
  return layout;
}
