/* Copyright 2024 Marimo. All rights reserved. */
import * as React from "react";
import { invariant } from "@/utils/invariant";
import { IslandsPyodideBridge } from "../islands/bridge";
import { isIslands } from "../islands/utils";
import { isStaticNotebook } from "../static/static-state";
import { PyodideBridge } from "../wasm/bridge";
import { isWasm } from "../wasm/utils";
import { createNetworkRequests } from "./requests-network";
import { createStaticRequests } from "./requests-static";
import { createErrorToastingRequests } from "./requests-toasting";
import type {
  EditRequests,
  RunRequests,
  SetCellConfigRequest,
  SaveUserConfigurationRequest,
  FileCreateRequest,
  CodeCompletionRequest,
} from "./types";

export const RequestClientContext = React.createContext<
  null | (EditRequests & RunRequests)
>(null);

export function useRequestClient() {
  const context = React.useContext(RequestClientContext);
  invariant(
    context,
    "sueRequestClient() must be used within <RequestClientContext.Provider>.",
  );
  return context;
}

export function resolveRequestClient(): EditRequests & RunRequests {
  if (isIslands()) {
    // We don't wrap in error toasting, since we don't currently mount
    // the ToastProvider in islands
    return IslandsPyodideBridge.INSTANCE;
  }
  const base = isWasm()
    ? PyodideBridge.INSTANCE
    : isStaticNotebook()
      ? createStaticRequests()
      : createNetworkRequests();
  return createErrorToastingRequests(base);
}

// Standalone utility functions for legacy code
export function saveCellConfig(request: SetCellConfigRequest) {
  return resolveRequestClient().saveCellConfig(request);
}

export function saveUserConfig(request: SaveUserConfigurationRequest) {
  return resolveRequestClient().saveUserConfig(request);
}

export function sendCreateFileOrFolder(request: FileCreateRequest) {
  return resolveRequestClient().sendCreateFileOrFolder(request);
}

export function sendCodeCompletionRequest(request: CodeCompletionRequest) {
  return resolveRequestClient().sendCodeCompletionRequest(request);
}
