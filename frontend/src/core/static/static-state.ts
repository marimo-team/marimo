/* Copyright 2023 Marimo. All rights reserved. */
import { invariant } from "@/utils/invariant";
import {
  MarimoStaticState,
  StaticNotebookState,
  StaticVirtualFiles,
} from "./types";

declare global {
  interface Window {
    __MARIMO_STATIC__?: MarimoStaticState;
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

export function getStaticVirtualFiles(): StaticVirtualFiles {
  invariant(window.__MARIMO_STATIC__ !== undefined, "Not a static notebook");

  return window.__MARIMO_STATIC__.files;
}
