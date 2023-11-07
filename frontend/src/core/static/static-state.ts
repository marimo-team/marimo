/* Copyright 2023 Marimo. All rights reserved. */
import { invariant } from "@/utils/invariant";
import { NotebookState } from "../state/cells";

export interface StaticNotebookState
  extends Pick<NotebookState, "cellIds" | "cellData" | "cellRuntime"> {
  version: string;
  assetUrl: string;
}

declare global {
  interface Window {
    __MARIMO_STATIC__?: {
      version: string;
      notebookState: StaticNotebookState;
      assetUrl: string;
    };
  }
}

export function parseStaticState(): StaticNotebookState {
  invariant(window.__MARIMO_STATIC__ !== undefined, "Not a static notebook");

  return window.__MARIMO_STATIC__.notebookState;
}

export function isStaticNotebook(): boolean {
  return (
    typeof window !== "undefined" && window.__MARIMO_STATIC__ !== undefined
  );
}

export function getStaticNotebookAssetUrl(): string {
  invariant(window.__MARIMO_STATIC__ !== undefined, "Not a static notebook");

  return window.__MARIMO_STATIC__.assetUrl;
}
