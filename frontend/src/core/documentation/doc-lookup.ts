/* Copyright 2026 Marimo. All rights reserved. */

import { getCells } from "@/core/cells/cells";
import { AUTOCOMPLETER } from "@/core/codemirror/completion/Autocompleter";
import { store } from "@/core/state/jotai";
import { Logger } from "@/utils/Logger";
import { documentationAtom } from "./state";

/**
 * Request documentation for a qualified Python name (e.g. "torch.nn.Linear")
 * by piggybacking on the existing code-completion system.
 *
 * We send the qualified name as the "document" to the autocomplete endpoint.
 * Jedi resolves it and returns the docstring in the completion info.
 */
export async function requestOutputDocumentation(
  qualifiedName: string,
): Promise<void> {
  // We need any valid cell_id for the completion request.
  const cellId = getCells().inOrderIds.at(0);
  if (!cellId) {
    return;
  }

  try {
    const message = await AUTOCOMPLETER.request({
      document: qualifiedName,
      cellId,
    });

    if (!message || message.options.length === 0) {
      return;
    }

    // Find the option matching the last segment of the qualified name
    const shortName = qualifiedName.split(".").pop() ?? qualifiedName;

    const defaultOption = message.options[0];
    const match =
      message.options.find((o) => o.name === shortName) ?? defaultOption;

    if (match?.completion_info) {
      store.set(documentationAtom, {
        documentation: match.completion_info,
      });
    }
  } catch (error) {
    Logger.debug(`Doc lookup failed for "${qualifiedName}"`, error);
  }
}
