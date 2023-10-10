/* Copyright 2023 Marimo. All rights reserved. */
import { Logger } from "@/utils/Logger";
import { CellId } from "../model/ids";
import { TypedString } from "../model/typed";
import { Objects } from "@/utils/objects";
import { repl } from "@/utils/repl";

export type DataLocatorId = TypedString<"DataLocatorId">;

/**
 * Registry to track UIElement values.
 */
export class UIElementDataRegistry {
  /**
   * Shared singleton instance.
   */
  static readonly INSTANCE = new UIElementDataRegistry();

  private constructor() {
    repl(this, "UI_ELEMENT_DATA_REGISTRY");
  }

  // We want fast lookups by DataLocatorId and fast removals by CellId.
  private data = new Map<DataLocatorId, unknown>();
  private removeHandlers = new Map<CellId, () => void>();

  /**
   * Set the datastore for a Cell.
   */
  setValue(
    cellId: CellId,
    dataStore: Record<DataLocatorId, unknown> | undefined
  ) {
    // If there is already a remove handler for this cell, call it to remove
    // the old values.
    this.removeHandlers.get(cellId)?.();

    if (!dataStore) {
      return;
    }

    for (const [name, value] of Objects.entries(dataStore)) {
      const dataLocatorId = name as DataLocatorId;
      this.data.set(dataLocatorId, value);
    }
    this.removeHandlers.set(cellId, () => {
      Objects.keys(dataStore).forEach((dataLocatorId) => {
        this.data.delete(dataLocatorId);
      });
    });
  }

  /**
   * Get the value for a DataLocatorId
   */
  getValue<T>(dataLocatorId: DataLocatorId): T {
    if (!this.data.has(dataLocatorId)) {
      Logger.warn(`No value found for ${dataLocatorId}`);
    }
    return this.data.get(dataLocatorId) as T;
  }

  /**
   * Remove the value for a UIElement.
   */
  removeDataStore(cellId: CellId) {
    this.removeHandlers.get(cellId)?.();
  }
}
