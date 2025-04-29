/* Copyright 2024 Marimo. All rights reserved. */
import { filenameAtom } from "@/core/saving/filenameAtom";
import { store } from "@/core/state/jotai";
import type { ZodType, ZodTypeDef } from "zod";

export class TypedLocalStorage<T> {
  constructor(
    private key: string,
    private defaultValue: T,
  ) {}

  get(): T {
    try {
      const item = window.localStorage.getItem(this.key);
      return item ? (JSON.parse(item) as T) : this.defaultValue;
    } catch {
      return this.defaultValue;
    }
  }

  set(value: T) {
    window.localStorage.setItem(this.key, JSON.stringify(value));
  }
}

export class ZodLocalStorage<T> {
  constructor(
    protected key: string,
    private schema: ZodType<T, ZodTypeDef, unknown>,
    private getDefaultValue: () => T,
  ) {}

  get(): T {
    try {
      const item = window.localStorage.getItem(this.key);
      return item
        ? this.schema.parse(JSON.parse(item))
        : this.getDefaultValue();
    } catch {
      return this.getDefaultValue();
    }
  }

  set(value: T) {
    window.localStorage.setItem(this.key, JSON.stringify(value));
  }

  remove() {
    window.localStorage.removeItem(this.key);
  }
}

/**
 * A ZodLocalStorage that is scoped to the current notebook filename.
 * Useful for storing notebook-specific settings, such as column widths.
 */
export class NotebookScopedLocalStorage<T> extends ZodLocalStorage<T> {
  private filename: string | null;
  private baseKey: string;
  private unsubscribeFromFilename: (() => void) | null;

  constructor(
    key: string,
    schema: ZodType<T, ZodTypeDef, unknown>,
    getDefaultValue: () => T,
  ) {
    const filename = store.get(filenameAtom);
    const scopedKey = filename ? `${key}:${filename}` : key;
    super(scopedKey, schema, getDefaultValue);
    this.filename = filename;
    this.baseKey = key;

    try {
      this.unsubscribeFromFilename = store.sub(filenameAtom, () => {
        const newFilename = store.get(filenameAtom);
        this.handleFilenameChange(newFilename);
      });
    } catch {
      this.unsubscribeFromFilename = null;
    }
  }

  private createScopedKey(filename: string | null) {
    return filename ? `${this.baseKey}:${filename}` : this.baseKey;
  }

  private handleFilenameChange(newFilename: string | null) {
    if (newFilename && newFilename !== this.filename) {
      const currentValue = this.get();
      this.remove();

      this.filename = newFilename;
      this.key = this.createScopedKey(newFilename);
      this.set(currentValue);
    }
  }

  // Used in testing
  public getKey() {
    return this.key;
  }

  // Used in testing. Can also call in cleanup functions
  public dispose() {
    if (this.unsubscribeFromFilename) {
      this.unsubscribeFromFilename();
      this.unsubscribeFromFilename = null;
    }
  }
}
