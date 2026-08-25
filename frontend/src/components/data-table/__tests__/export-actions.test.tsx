/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import { buildDownloadAsRequest, sourceFormatForCopy } from "../export-actions";

const PT_BR_LOCALE = { tag: "pt-BR", decimal_separator: "," };

describe("buildDownloadAsRequest", () => {
  it("includes locale for CSV and TSV", () => {
    expect(buildDownloadAsRequest("csv", "pt-BR")).toEqual({
      format: "csv",
      locale: PT_BR_LOCALE,
    });
    expect(buildDownloadAsRequest("tsv", "pt-BR")).toEqual({
      format: "tsv",
      locale: PT_BR_LOCALE,
    });
  });

  it("omits locale for JSON and Parquet", () => {
    expect(buildDownloadAsRequest("json", "pt-BR")).toEqual({ format: "json" });
    expect(buildDownloadAsRequest("parquet", "pt-BR")).toEqual({
      format: "parquet",
    });
  });
});

describe("file and clipboard request parity", () => {
  it("sends the same locale for CSV download and clipboard copy", () => {
    const download = buildDownloadAsRequest("csv", "pt-BR");
    const clipboard = buildDownloadAsRequest(
      sourceFormatForCopy("csv"),
      "pt-BR",
    );
    expect(download).toEqual({ format: "csv", locale: PT_BR_LOCALE });
    expect(clipboard).toEqual(download);
  });

  it("sends the same locale for TSV download and clipboard copy", () => {
    const download = buildDownloadAsRequest("tsv", "pt-BR");
    const clipboard = buildDownloadAsRequest(
      sourceFormatForCopy("tsv"),
      "pt-BR",
    );
    expect(download).toEqual({ format: "tsv", locale: PT_BR_LOCALE });
    expect(clipboard).toEqual(download);
  });

  it("omits locale for JSON, Parquet, and Markdown source requests", () => {
    expect(buildDownloadAsRequest("json", "pt-BR")).toEqual({ format: "json" });
    expect(buildDownloadAsRequest("parquet", "pt-BR")).toEqual({
      format: "parquet",
    });
    expect(
      buildDownloadAsRequest(sourceFormatForCopy("json"), "pt-BR"),
    ).toEqual({ format: "json" });
    expect(
      buildDownloadAsRequest(sourceFormatForCopy("markdown"), "pt-BR"),
    ).toEqual({ format: "json" });
  });
});
