/* Copyright 2024 Marimo. All rights reserved. */
import { describe, it, expect } from "vitest";
import { extractTimezone } from "../types";

describe("extractTimezone", () => {
  it("should return undefined when dtype is undefined", () => {
    expect(extractTimezone(undefined)).toBe(undefined);
  });

  it("should return undefined when dtype is not a datetime with timezone", () => {
    expect(extractTimezone("string")).toBe(undefined);
    expect(extractTimezone("int64")).toBe(undefined);
    expect(extractTimezone("float64")).toBe(undefined);
    expect(extractTimezone("date")).toBe(undefined);
    expect(extractTimezone("datetime")).toBe(undefined);
    expect(extractTimezone("datetime[]")).toBe(undefined);
  });

  it("should return the timezone for datetime with timezone format", () => {
    expect(extractTimezone("datetime[ns,UTC]")).toBe("UTC");
    expect(extractTimezone("datetime[ns,US/Eastern]")).toBe("US/Eastern");
    expect(extractTimezone("datetime[ms,Europe/London]")).toBe("Europe/London");
    expect(extractTimezone("datetime[s,UTC]")).toBe("UTC");
    expect(extractTimezone("datetime[s,US/Eastern]")).toBe("US/Eastern");
    expect(extractTimezone("datetime[s,Europe/London]")).toBe("Europe/London");
    expect(extractTimezone("datetime[m,UTC]")).toBe("UTC");
    expect(extractTimezone("datetime[m,US/Eastern]")).toBe("US/Eastern");
    expect(extractTimezone("datetime[m,Europe/London]")).toBe("Europe/London");
  });
});
