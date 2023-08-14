/* Copyright 2023 Marimo. All rights reserved. */
import { CompletionContext, CompletionResult } from "@codemirror/autocomplete";

import { Deferred } from "../../../utils/Deferred";
import { COMPLETION_REQUESTS } from "./CompletionRequests";
import { sendCodeCompletionRequest } from "../../network/requests";
import { generateUUID } from "../../../utils/uuid";
import { Logger } from "../../../utils/Logger";
import { HTMLCellId } from "@/core/model/ids";

export function completer(context: CompletionContext) {
  const query = context.state.doc.sliceString(0, context.pos);
  const element = document.activeElement;
  let cellId = null;
  if (element !== null) {
    const cellContainer = HTMLCellId.findElement(element);
    if (cellContainer !== null) {
      cellId = HTMLCellId.parse(cellContainer.id);
    }
  }

  if (cellId === null) {
    Logger.error("Failed to find active cell.");
    return null;
  }

  const completionId = generateUUID();
  const deferred = new Deferred<CompletionResult>();
  COMPLETION_REQUESTS.register(completionId, deferred, context.pos);
  sendCodeCompletionRequest(completionId, query, cellId);
  return deferred.promise;
}
