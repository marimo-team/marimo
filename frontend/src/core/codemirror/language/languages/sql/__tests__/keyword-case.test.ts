/* Copyright 2026 Marimo. All rights reserved. */

import { afterEach, describe, expect, it } from "vitest";
import { userConfigAtom } from "@/core/config/config";
import {
  defaultUserConfig,
  type SqlKeywordCase,
} from "@/core/config/config-schema";
import { store } from "@/core/state/jotai";
import { sqlKeyword, sqlKeywordCase } from "../keyword-case";

function setKeywordCase(keywordCase: SqlKeywordCase | undefined) {
  const config = defaultUserConfig();
  store.set(userConfigAtom, {
    ...config,
    runtime: { ...config.runtime, sql_keyword_case: keywordCase },
  });
}

describe("sqlKeywordCase", () => {
  afterEach(() => {
    store.set(userConfigAtom, defaultUserConfig());
  });

  it("defaults to upper", () => {
    store.set(userConfigAtom, defaultUserConfig());
    expect(sqlKeywordCase()).toBe("upper");
    expect(sqlKeyword("select")).toBe("SELECT");
  });

  it("returns lower when configured", () => {
    setKeywordCase("lower");
    expect(sqlKeywordCase()).toBe("lower");
    expect(sqlKeyword("SELECT TOP")).toBe("select top");
  });

  it("falls back to upper when the setting is missing", () => {
    setKeywordCase(undefined);
    expect(sqlKeywordCase()).toBe("upper");
    expect(sqlKeyword("limit")).toBe("LIMIT");
  });
});
