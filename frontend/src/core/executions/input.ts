/* Copyright 2026 Marimo. All rights reserved. */

/** Answer a prompt the runtime is waiting on. */

import type * as Protocol from "@marimo-team/client/protocol";
import type { createStore } from "jotai";
import { toast } from "@/components/ui/use-toast";
import { activeNotebookReplicaAtom } from "@/core/session/active-notebook";
import { prettyError } from "@/utils/errors";
import { Logger } from "@/utils/Logger";

type Store = ReturnType<typeof createStore>;

/**
 * Send `value` to the host as the answer to the prompt `inputId`.
 *
 * The reply names its prompt, so the host marks that prompt answered for
 * every client and refuses a reply to one that has already been answered
 * or cancelled. A refusal is reported, since the user typed the answer and
 * would otherwise wait on a prompt that is not going to take it.
 */
export async function replyInput(
  store: Store,
  inputId: Protocol.ItemId,
  value: string,
): Promise<void> {
  const replica = store.get(activeNotebookReplicaAtom);
  const notebook = replica === null ? null : store.get(replica.notebookAtom);
  const backend = replica === null ? null : store.get(replica.backendAtom);
  if (notebook === null || backend === null) {
    Logger.warn("No notebook is connected to answer the prompt in");
    return;
  }
  try {
    const result = await backend
      .notebook(notebook.id)
      .input(inputId, { value });
    if (result.ok) {
      return;
    }
    Logger.error("The host refused the input reply", result.problem);
    toast({
      title: "Failed to send input",
      description: result.problem.detail ?? result.problem.title,
      variant: "danger",
    });
  } catch (error) {
    Logger.error("Failed to send input", error);
    toast({
      title: "Failed to send input",
      description: prettyError(error),
      variant: "danger",
    });
  }
}
