/* Copyright 2023 Marimo. All rights reserved. */
import { useEffect, useRef } from "react";
import { ConnectionStatus, WebSocketState } from "../websocket/types";
import { UserConfig } from "../config/config";

export function useAutoSave(opts: {
  codes: string[];
  config: UserConfig;
  connStatus: ConnectionStatus;
  needsSave: boolean;
  onSave: () => void;
}) {
  const { codes, config, connStatus, needsSave, onSave } = opts;
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
  }, [codes, config.save, connStatus.state, onSave, needsSave]);
}
