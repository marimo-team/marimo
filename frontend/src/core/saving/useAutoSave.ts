/* Copyright 2024 Marimo. All rights reserved. */
import { useEffect, useRef } from "react";
import type { UserConfig } from "../config/config-schema";
import type { CellConfig } from "../network/types";
import { type ConnectionStatus, WebSocketState } from "../websocket/types";

export function useAutoSave(opts: {
  codes: string[];
  cellConfigs: CellConfig[];
  cellNames: string[];
  config: UserConfig["save"];
  connStatus: ConnectionStatus;
  needsSave: boolean;
  kioskMode: boolean;
  onSave: () => void;
}) {
  const {
    codes,
    cellConfigs,
    config,
    connStatus,
    cellNames,
    needsSave,
    kioskMode,
    onSave,
  } = opts;
  const autosaveTimeoutId = useRef<NodeJS.Timeout | null>(null);

  const codesString = codes.join(":");
  const cellConfigsString = cellConfigs
    .map((config) => JSON.stringify(config))
    .join(":");
  const cellNamesString = cellNames.join(":");

  useEffect(() => {
    // If kiosk mode is enabled, do not autosave
    if (kioskMode) {
      return;
    }

    if (config.autosave === "after_delay") {
      if (autosaveTimeoutId.current !== null) {
        clearTimeout(autosaveTimeoutId.current);
      }

      if (needsSave && connStatus.state === WebSocketState.OPEN) {
        autosaveTimeoutId.current = setTimeout(onSave, config.autosave_delay);
      }
    }

    return () => {
      if (autosaveTimeoutId.current !== null) {
        clearTimeout(autosaveTimeoutId.current);
      }
    };
    // codes, cellConfigs, cellNames needed in deps array to prevent race condition
    // with needsSave when user changes state rapidly
  }, [
    codesString,
    cellConfigsString,
    cellNamesString,
    config,
    connStatus.state,
    onSave,
    kioskMode,
    needsSave,
  ]);
}
