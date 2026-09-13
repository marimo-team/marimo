/* Copyright 2026 Marimo. All rights reserved. */
import { useAtom, useAtomValue, useSetAtom } from "jotai";
import { Suspense, useEffect, useRef, useState } from "react";
import useEvent from "react-use-event-hook";
import { Spinner } from "@/components/icons/spinner";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { kernelStartupErrorAtom } from "@/core/errors/state";
import { connectionAtom } from "@/core/network/connection";
import { useRequestClient } from "@/core/network/requests";
import { invalidatePackageData } from "@/core/packages/package-data";
import {
  sandboxActionsAtom,
  sandboxAtom,
  sandboxSyncAtom,
} from "@/core/packages/sandbox-state";
import {
  showPackageRestartToast,
  showSandboxSyncToast,
} from "@/core/packages/toast-components";
import { useFilename } from "@/core/saving/filename";
import { waitFor } from "@/core/state/jotai";
import { isWasm } from "@/core/wasm/utils";
import { WebSocketState } from "@/core/websocket/types";
import { LazyAnyLanguageCodeMirror } from "@/plugins/impl/code/LazyAnyLanguageCodeMirror";
import { useTheme } from "@/theme/useTheme";
import { HTTPError, prettyError } from "@/utils/errors";
import { Paths } from "@/utils/paths";
import { SandboxErrorOutput } from "./sandbox-panel";

/** Lives with the editor so closing Packages does not discard a manifest draft. */
export function SandboxController({
  onReconnect,
}: {
  onReconnect: () => Promise<void>;
}) {
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
  const { theme } = useTheme();
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
    if (inFlight.current || connection.state === WebSocketState.CONNECTING) {
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
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent className="sm:max-w-xl grid-cols-1 max-h-[80vh] overflow-auto">
        <DialogHeader>
          <DialogTitle>Edit manifest</DialogTitle>
          <DialogDescription className="font-mono text-xs">
            {Paths.basename(filename ?? "Untitled notebook")} · script metadata
          </DialogDescription>
        </DialogHeader>
        {document && !loading ? (
          <Suspense fallback={<Spinner />}>
            <LazyAnyLanguageCodeMirror
              language="toml"
              theme={theme}
              value={document.draft}
              onChange={(draft) =>
                setDocument((value) => value && { ...value, draft })
              }
              editable={!pending}
              height="260px"
              basicSetup={{ lineNumbers: false, foldGutter: false }}
              className="border rounded overflow-hidden"
              aria-label="Notebook manifest"
            />
          </Suspense>
        ) : (
          !error && <Spinner />
        )}
        {diagnostic && <SandboxErrorOutput error={diagnostic} />}
        {conflict && (
          <Button variant="text" size="sm" onClick={loadManifest}>
            Discard draft and reload manifest
          </Button>
        )}
        <DialogFooter className="items-center sm:justify-between gap-3">
          <span className="text-xs text-muted-foreground mr-auto">
            {loading
              ? "Loading…"
              : dirty
                ? "Unsaved changes"
                : document
                  ? "Saved"
                  : ""}
          </span>
          <Button variant="text" size="sm" onClick={() => setOpen(false)}>
            Close
          </Button>
          <Button
            size="sm"
            disabled={!document || pending}
            onClick={saveAndSync}
          >
            {pending && <Spinner className="size-3 mr-2" />}
            {loading
              ? "Loading…"
              : saving
                ? "Saving…"
                : pending
                  ? "Syncing…"
                  : dirty
                    ? "Save & sync"
                    : "Sync"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
