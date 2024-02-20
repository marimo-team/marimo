/* Copyright 2024 Marimo. All rights reserved. */
import { ZodType, ZodTypeDef } from "zod";

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
    private key: string,
    private schema: ZodType<T, ZodTypeDef, unknown>,
    private defaultValue: T,
  ) {}

  get(): T {
    try {
      const item = window.localStorage.getItem(this.key);
      return item ? this.schema.parse(JSON.parse(item)) : this.defaultValue;
    } catch {
      return this.defaultValue;
    }
  }

  set(value: T) {
    window.localStorage.setItem(this.key, JSON.stringify(value));
  }
}
