/* Copyright 2024 Marimo. All rights reserved. */
import { useEffect, useRef } from "react";
import { ConnectionStatus, WebSocketState } from "../websocket/types";
import { UserConfig } from "../config/config-schema";
import { CellConfig } from "../cells/types";

export function useAutoSave(opts: {
  codes: string[];
  cellConfigs: CellConfig[];
  cellNames: string[];
  config: UserConfig;
  connStatus: ConnectionStatus;
  needsSave: boolean;
  onSave: () => void;
}) {
  const {
    codes,
    cellConfigs,
    config,
    connStatus,
    cellNames,
    needsSave,
    onSave,
  } = opts;
  const autosaveTimeoutId = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    if (config.save.autosave === "after_delay") {
      if (autosaveTimeoutId.current !== null) {
        clearTimeout(autosaveTimeoutId.current);
      }

      if (needsSave && connStatus.state === WebSocketState.OPEN) {
        autosaveTimeoutId.current = setTimeout(
          onSave,
          config.save.autosave_delay,
        );
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
    codes,
    cellConfigs,
    cellNames,
    config.save,
    connStatus.state,
    onSave,
    needsSave,
  ]);
}
