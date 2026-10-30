/* Copyright 2026 Marimo. All rights reserved. */
import { useEffect, useRef } from "react";
import type { UserConfig } from "../config/config-schema";
import { type ConnectionStatus, ConnectionState } from "../session/types";

/** Save after a delay while the notebook needs it, restarting on every confirmed change. */
export function useAutoSave(opts: {
  /** The document version, which counts confirmed changes. */
  version: number | null;
  config: UserConfig["save"];
  connStatus: ConnectionStatus;
  needsSave: boolean;
  canEdit: boolean;
  onSave: () => void;
}) {
  const { version, config, connStatus, needsSave, canEdit, onSave } = opts;
  const autosaveTimeoutId = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    if (!canEdit) {
      return;
    }

    if (config.autosave === "after_delay") {
      if (autosaveTimeoutId.current !== null) {
        clearTimeout(autosaveTimeoutId.current);
      }

      if (needsSave && connStatus.state === ConnectionState.OPEN) {
        autosaveTimeoutId.current = setTimeout(onSave, config.autosave_delay);
      }
    }

    return () => {
      if (autosaveTimeoutId.current !== null) {
        clearTimeout(autosaveTimeoutId.current);
      }
    };
    // `version` restarts the delay on every confirmed change.
  }, [version, config, connStatus.state, onSave, canEdit, needsSave]);
}
