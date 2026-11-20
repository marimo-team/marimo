/* Copyright 2026 Marimo. All rights reserved. */
import { useEffect } from "react";
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

  useEffect(() => {
    if (
      !canEdit ||
      config.autosave !== "after_delay" ||
      !needsSave ||
      connStatus.state !== ConnectionState.OPEN
    ) {
      return;
    }

    const timeout = setTimeout(onSave, config.autosave_delay);
    return () => clearTimeout(timeout);
    // `version` restarts the delay on every confirmed change.
  }, [version, config, connStatus.state, onSave, canEdit, needsSave]);
}
