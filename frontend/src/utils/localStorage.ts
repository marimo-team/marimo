/* Copyright 2024 Marimo. All rights reserved. */

import type { ZodType, ZodTypeDef } from "zod";
import { filenameAtom } from "@/core/saving/file-state";
import { store } from "@/core/state/jotai";
import { Logger } from "./Logger";

interface Storage<T> {
  get(key: string): T;
  set(key: string, value: T): void;
  remove(key: string): void;
}

export class TypedLocalStorage<T> implements Storage<T> {
  constructor(private defaultValue: T) {}

  get(key: string): T {
    try {
      const item = globalThis.localStorage.getItem(key);
      return item ? (JSON.parse(item) as T) : this.defaultValue;
    } catch {
      return this.defaultValue;
    }
  }

  set(key: string, value: T) {
    globalThis.localStorage.setItem(key, JSON.stringify(value));
  }

  remove(key: string) {
    globalThis.localStorage.removeItem(key);
  }
}

export class ZodLocalStorage<T> implements Storage<T> {
  constructor(
    private schema: ZodType<T, ZodTypeDef, unknown>,
    private getDefaultValue: () => T,
  ) {}

  get(key: string): T {
    try {
      const item = globalThis.localStorage.getItem(key);
      if (item == null) {
        return this.getDefaultValue();
      }
      const result = this.schema.safeParse(JSON.parse(item));
      if (!result.success) {
        Logger.warn("Error parsing zod local storage", result.error);
        return this.getDefaultValue();
      }
      return result.data;
    } catch (error) {
      Logger.warn("Error getting zod local storage", error);
      return this.getDefaultValue();
    }
  }

  set(key: string, value: T) {
    globalThis.localStorage.setItem(key, JSON.stringify(value));
  }

  remove(key: string) {
    globalThis.localStorage.removeItem(key);
  }
}

/**
 * A ZodLocalStorage that is scoped to the current notebook filename.
 * Useful for storing notebook-specific settings, such as column widths.
 */
export class NotebookScopedLocalStorage<T> extends ZodLocalStorage<T> {
  private filename: string | null;
  private unsubscribeFromFilename: (() => void) | null;

  constructor(
    key: string,
    schema: ZodType<T, ZodTypeDef, unknown>,
    getDefaultValue: () => T,
  ) {
    const filename = store.get(filenameAtom);
    super(schema, getDefaultValue);
    this.filename = filename;

    try {
      this.unsubscribeFromFilename = store.sub(filenameAtom, () => {
        const newFilename = store.get(filenameAtom);
        this.handleFilenameChange(key, newFilename);
      });
    } catch {
      this.unsubscribeFromFilename = null;
    }
  }

  override get(key: string) {
    return super.get(this.createScopedKey(key, this.filename));
  }

  override set(key: string, value: T) {
    super.set(this.createScopedKey(key, this.filename), value);
  }

  override remove(key: string) {
    super.remove(this.createScopedKey(key, this.filename));
  }

  /**
   * @visibleForTesting
   */
  public createScopedKey(key: string, filename: string | null) {
    return filename ? `${key}:${filename}` : key;
  }

  private handleFilenameChange(key: string, newFilename: string | null) {
    if (newFilename && newFilename !== this.filename) {
      const currentValue = this.get(key);
      this.remove(key);

      // update filename before setting the value
      this.filename = newFilename;
      this.set(key, currentValue);
    }
  }

  // Used in testing. Can also call in cleanup functions
  public dispose() {
    if (this.unsubscribeFromFilename) {
      this.unsubscribeFromFilename();
      this.unsubscribeFromFilename = null;
    }
  }
}
