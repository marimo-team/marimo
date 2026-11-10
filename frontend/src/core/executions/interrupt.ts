/* Copyright 2026 Marimo. All rights reserved. */

import type { createStore } from "jotai";
import { toast } from "@/components/ui/use-toast";
import { activeNotebookReplicaAtom } from "@/core/session/active-notebook";
import { prettyError } from "@/utils/errors";
import { Logger } from "@/utils/Logger";

/** Interrupt active runtime work and end queued runs. */
export async function interruptRuntime(
  store: ReturnType<typeof createStore>,
): Promise<void> {
  const replica = store.get(activeNotebookReplicaAtom);
  if (replica === null) {
    return;
  }
  const notebook = store.get(replica.notebookAtom);
  const backend = store.get(replica.backendAtom);
  if (notebook === null || backend === null) {
    return;
  }
  try {
    const result = await backend.notebook(notebook.id).interrupt();
    if (result.ok) {
      return;
    }
    // The runtime can stop before the request arrives.
    if (result.status === 409 || result.status === 404) {
      return;
    }
    if (result.status === 403) {
      Logger.warn("Interrupt refused, connection is read-only", result.problem);
      return;
    }
    Logger.error("The host refused the interrupt", result.problem);
    toast({
      title: "Failed to interrupt",
      description: result.problem.detail ?? result.problem.title,
      variant: "danger",
    });
  } catch (error) {
    Logger.error("Failed to interrupt", error);
    toast({
      title: "Failed to interrupt",
      description: prettyError(error),
      variant: "danger",
    });
  }
}
