/* Copyright 2023 Marimo. All rights reserved. */
import { useEffect, useRef } from "react";
import { ConnectionStatus, WebSocketState } from "../websocket/types";
import { UserConfig } from "../config/config";
import { CellConfig } from "../model/cells";

export function useAutoSave(opts: {
  codes: string[];
  cellConfigs: CellConfig[];
  config: UserConfig;
  connStatus: ConnectionStatus;
  needsSave: boolean;
  onSave: () => void;
}) {
  const { codes, cellConfigs, config, connStatus, needsSave, onSave } = opts;
  const autosaveTimeoutId = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    if (config.save.autosave === "after_delay") {
      if (autosaveTimeoutId.current !== null) {
        clearTimeout(autosaveTimeoutId.current);
      }

      if (needsSave && connStatus.state === WebSocketState.OPEN) {
        autosaveTimeoutId.current = setTimeout(
          onSave,
          config.save.autosave_delay
        );
      }
    }

    return () => {
      if (autosaveTimeoutId.current !== null) {
        clearTimeout(autosaveTimeoutId.current);
      }
    };
    // codes, cellConfigs needed in deps array to prevent race condition
    // with needsSave when user changes state rapidly
  }, [codes, cellConfigs, config.save, connStatus.state, onSave, needsSave]);
}
