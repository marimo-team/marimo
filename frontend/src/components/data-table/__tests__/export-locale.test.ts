/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import { resolveExportLocale } from "../export-locale";
import { DownloadAsSchema } from "../schemas";

describe("resolveExportLocale", () => {
  it("resolves a decimal point for en-US", () => {
    expect(resolveExportLocale("en-US")).toEqual({
      tag: "en-US",
      decimal_separator: ".",
    });
  });

  it("resolves a decimal comma for pt-BR", () => {
    expect(resolveExportLocale("pt-BR").decimal_separator).toBe(",");
  });

  it("preserves a non-comma Unicode decimal separator", () => {
    expect(resolveExportLocale("ar-EG").decimal_separator).toBe("٫");
  });

  it("rejects an invalid locale", () => {
    expect(() => resolveExportLocale("not_a_locale")).toThrow();
  });

  it("rejects an empty locale tag", () => {
    expect(() => resolveExportLocale("")).toThrow();
  });
});

describe("DownloadAsSchema", () => {
  it("accepts a request with only format", () => {
    expect(DownloadAsSchema.input.parse({ format: "csv" })).toEqual({
      format: "csv",
    });
  });

  it("accepts an optional locale value", () => {
    const locale = { tag: "pt-BR", decimal_separator: "," };
    expect(DownloadAsSchema.input.parse({ format: "csv", locale })).toEqual({
      format: "csv",
      locale,
    });
  });
});
