/* Copyright 2026 Marimo. All rights reserved. */
import { Suspense } from "react";
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
import { useSandboxController } from "@/core/packages/useSandboxController";
import { LazyAnyLanguageCodeMirror } from "@/plugins/impl/code/LazyAnyLanguageCodeMirror";
import { useTheme } from "@/theme/useTheme";
import { Paths } from "@/utils/paths";
import { SandboxErrorOutput } from "./sandbox-panel";

export function SandboxController({
  onReconnect,
}: {
  onReconnect: () => Promise<void>;
}) {
  const {
    filename,
    open,
    setOpen,
    draft,
    setDraft,
    dirty,
    loading,
    saving,
    pending,
    error,
    diagnostic,
    conflict,
    loadManifest,
    saveAndSync,
  } = useSandboxController(onReconnect);
  const { theme } = useTheme();
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent className="sm:max-w-xl grid-cols-1 max-h-[80vh] overflow-auto">
        <DialogHeader>
          <DialogTitle>Edit manifest</DialogTitle>
          <DialogDescription className="font-mono text-xs">
            {Paths.basename(filename ?? "Untitled notebook")} · script metadata
          </DialogDescription>
        </DialogHeader>
        {draft !== null && !loading ? (
          <Suspense fallback={<Spinner />}>
            <LazyAnyLanguageCodeMirror
              language="toml"
              theme={theme}
              value={draft}
              onChange={setDraft}
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
                : draft !== null
                  ? "Saved"
                  : ""}
          </span>
          <Button variant="text" size="sm" onClick={() => setOpen(false)}>
            Close
          </Button>
          <Button
            size="sm"
            disabled={draft === null || pending}
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
