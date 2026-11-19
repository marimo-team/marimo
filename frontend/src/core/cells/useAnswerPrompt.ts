/* Copyright 2026 Marimo. All rights reserved. */
import { useStore } from "jotai";
import useEvent from "react-use-event-hook";
import { Logger } from "@/utils/Logger";
import { replyInput } from "@/core/executions";
import { consoleExecution } from "./execution-console";
import { useCellActions } from "./actions";
import type { CellId } from "./ids";

/** Show the local answer once the host accepts it for this prompt. */
export function useAnswerPrompt(cellId: CellId) {
  const store = useStore();
  const actions = useCellActions();
  return useEvent(async (text: string, inputId?: string) => {
    if (inputId === undefined) {
      Logger.error("The prompt has no id to answer it by");
      return;
    }
    const item = consoleExecution(store.get, cellId)?.items.get(inputId);
    if (
      (await replyInput(store, inputId, text)) &&
      item?.kind === "input" &&
      !item.password &&
      consoleExecution(store.get, cellId)?.record.id === item.execution_id
    ) {
      actions.setStdinResponse({ cellId, response: text, inputId });
    }
  });
}
