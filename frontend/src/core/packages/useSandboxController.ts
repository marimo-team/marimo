/* Copyright 2026 Marimo. All rights reserved. */
import { useAtom, useAtomValue, useSetAtom } from "jotai";
import { useEffect, useRef, useState } from "react";
import useEvent from "react-use-event-hook";
import { kernelStartupErrorAtom } from "@/core/errors/state";
import { connectionAtom } from "@/core/network/connection";
import { useRequestClient } from "@/core/network/requests";
import { useFilename } from "@/core/saving/filename";
import { waitFor } from "@/core/state/jotai";
import { isWasm } from "@/core/wasm/utils";
import { WebSocketState } from "@/core/websocket/types";
import { HTTPError, prettyError } from "@/utils/errors";
import { invalidatePackageData } from "./package-data";
import {
  sandboxActionsAtom,
  sandboxAtom,
  sandboxSyncAtom,
} from "./sandbox-state";
import {
  showPackageRestartToast,
  showSandboxSyncToast,
} from "./toast-components";

/** Mount once with the editor so manifest drafts survive closing Packages. */
export function useSandboxController(onReconnect: () => Promise<void>) {
  const requests = useRequestClient();
  const filename = useFilename();
  const connection = useAtomValue(connectionAtom);
  const startupError = useAtomValue(kernelStartupErrorAtom);
  const setSandbox = useSetAtom(sandboxAtom);
  const [operation, setOperation] = useAtom(sandboxSyncAtom);
  const setActions = useSetAtom(sandboxActionsAtom);
  const [open, setOpen] = useState(false);
  const [document, setDocument] = useState<{
    original: string;
    draft: string;
  } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(false);
  const [conflict, setConflict] = useState(false);
  const inFlight = useRef(false);
  const dirty = document !== null && document.original !== document.draft;

  useEffect(() => {
    if (isWasm()) {
      return;
    }
    let cancelled = false;
    requests
      .getSandbox({ fileKey: filename })
      .then((value) => {
        if (!cancelled) {
          setSandbox(value);
        }
      })
      .catch(() => {
        /* A connection error is already shown by the editor. */
      });
    return () => {
      cancelled = true;
    };
  }, [requests, filename, connection.state, setSandbox]);

  const sync = useEvent(async () => {
    if (
      inFlight.current ||
      operation.pending ||
      connection.state === WebSocketState.CONNECTING
    ) {
      return false;
    }
    inFlight.current = true;
    setOperation((value) => ({ ...value, pending: true, error: null }));
    try {
      const result = await requests.syncSandbox({ fileKey: filename });
      if (result.restartRequired) {
        showPackageRestartToast();
      }
      if (!result.success) {
        throw new Error(result.error ?? "Sandbox sync failed.");
      }
      if (result.reconnect) {
        await onReconnect();
        const status = await waitFor(
          connectionAtom,
          (value) =>
            value.state === WebSocketState.OPEN ||
            value.state === WebSocketState.CLOSED,
        );
        if (status.state === WebSocketState.CLOSED) {
          return false;
        }
      }
      if (!result.reconnect) {
        invalidatePackageData();
      }
      showSandboxSyncToast();
      return true;
    } catch (cause) {
      setOperation((value) => ({ ...value, error: prettyError(cause) }));
      return false;
    } finally {
      inFlight.current = false;
      setOperation((value) => ({ ...value, pending: false }));
    }
  });

  const loadManifest = useEvent(async () => {
    setLoading(true);
    setError(null);
    setConflict(false);
    try {
      const result = await requests.getSandbox({ fileKey: filename });
      setSandbox(result);
      if (result.manifest === null) {
        throw new Error("No notebook manifest is available yet.");
      }
      setDocument({ original: result.manifest, draft: result.manifest });
    } catch (cause) {
      setError(prettyError(cause));
    } finally {
      setLoading(false);
    }
  });

  const editManifest = useEvent(async () => {
    setOpen(true);
    if (!dirty) {
      await loadManifest();
    }
  });

  useEffect(() => {
    setActions({ sync, editManifest });
    return () => {
      setActions(null);
    };
  }, [sync, editManifest, setActions]);

  const saveAndSync = async () => {
    if (!document || loading || saving || operation.pending) {
      return;
    }
    setSaving(true);
    setError(null);
    try {
      if (dirty) {
        const result = await requests.updateManifest({
          fileKey: filename,
          contents: document.draft,
          previous: document.original,
        });
        setSandbox(result);
        if (result.manifest !== null) {
          setDocument({ original: result.manifest, draft: result.manifest });
        }
      }
      if (await sync()) {
        setOpen(false);
      }
    } catch (cause) {
      setError(prettyError(cause));
      setConflict(cause instanceof HTTPError && cause.status === 409);
    } finally {
      setSaving(false);
    }
  };
  const pending =
    saving ||
    loading ||
    operation.pending ||
    connection.state === WebSocketState.CONNECTING;
  const diagnostic = error ?? operation.error ?? startupError;
  return {
    filename,
    open,
    setOpen,
    draft: document?.draft ?? null,
    setDraft: (draft: string) =>
      setDocument((value) => value && { ...value, draft }),
    dirty,
    loading,
    saving,
    pending,
    error,
    diagnostic,
    conflict,
    loadManifest,
    saveAndSync,
  };
}
