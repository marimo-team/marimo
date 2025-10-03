/* Copyright 2024 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import { formatBytes, formatTime } from "../formatting";

const locale = "en-US";

describe("formatBytes", () => {
  it("should format 0 bytes", () => {
    expect(formatBytes(0, locale)).toBe("0 B");
    expect(formatBytes(-1, locale)).toBe("0 B");
  });

  it("should format bytes", () => {
    expect(formatBytes(100, locale)).toBe("100 B");
    expect(formatBytes(512, locale)).toBe("512 B");
    expect(formatBytes(1023, locale)).toBe("1,023 B");
  });

  it("should format kilobytes", () => {
    expect(formatBytes(1024, locale)).toBe("1 KB");
    expect(formatBytes(1536, locale)).toBe("1.5 KB");
    expect(formatBytes(10240, locale)).toBe("10 KB");
  });

  it("should format megabytes", () => {
    expect(formatBytes(1048576, locale)).toBe("1 MB"); // 1024^2
    expect(formatBytes(1572864, locale)).toBe("1.5 MB"); // 1.5 * 1024^2
    expect(formatBytes(10485760, locale)).toBe("10 MB");
  });

  it("should format gigabytes", () => {
    expect(formatBytes(1073741824, locale)).toBe("1 GB"); // 1024^3
    expect(formatBytes(1610612736, locale)).toBe("1.5 GB"); // 1.5 * 1024^3
    expect(formatBytes(10737418240, locale)).toBe("10 GB");
  });

  it("should format terabytes", () => {
    expect(formatBytes(1099511627776, locale)).toBe("1 TB"); // 1024^4
    expect(formatBytes(1649267441664, locale)).toBe("1.5 TB"); // 1.5 * 1024^4
  });

  it("should respect locale parameter", () => {
    // German locale uses different separators
    const bytes = 1536; // 1.5 KB
    expect(formatBytes(bytes, "de-DE", locale)).toContain("1,5");
    // US locale uses dot
    expect(formatBytes(bytes, "en-US", locale)).toContain("1.5");
  });
});

describe("formatTime", () => {
  it("should format 0 seconds", () => {
    expect(formatTime(0, locale)).toBe("0s");
  });

  it("should format microseconds", () => {
    expect(formatTime(0.0000001, locale)).toBe("0.1µs");
    expect(formatTime(0.0000005, locale)).toBe("0.5µs");
    expect(formatTime(0.000000999, locale)).toBe("1µs"); // rounded by prettyNumber
  });

  it("should format milliseconds", () => {
    expect(formatTime(0.001, locale)).toBe("1ms");
    expect(formatTime(0.0015, locale)).toBe("1.5ms");
    expect(formatTime(0.1, locale)).toBe("100ms");
    expect(formatTime(0.5, locale)).toBe("500ms");
    expect(formatTime(0.999, locale)).toBe("999ms");
  });

  it("should format seconds", () => {
    expect(formatTime(1, locale)).toBe("1s");
    expect(formatTime(1.5, locale)).toBe("1.5s");
    expect(formatTime(30, locale)).toBe("30s");
    expect(formatTime(59.9, locale)).toBe("59.9s");
  });

  it("should format minutes and seconds", () => {
    expect(formatTime(60, locale)).toBe("1m");
    expect(formatTime(90, locale)).toBe("1m 30s");
    expect(formatTime(150, locale)).toBe("2m 30s");
    expect(formatTime(3540, locale)).toBe("59m");
    expect(formatTime(3599, locale)).toBe("59m 59s");
  });

  it("should format hours and minutes", () => {
    expect(formatTime(3600, locale)).toBe("1h");
    expect(formatTime(3660, locale)).toBe("1h 1m");
    expect(formatTime(5400, locale)).toBe("1h 30m");
    expect(formatTime(7200, locale)).toBe("2h");
    expect(formatTime(9000, locale)).toBe("2h 30m");
  });

  it("should respect locale parameter", () => {
    // German locale uses comma for decimal separator
    const time = 1.5;
    expect(formatTime(time, "de-DE")).toContain("1,5");
    // US locale uses dot
    expect(formatTime(time, "en-US")).toContain("1.5");
  });

  it("should handle edge cases", () => {
    expect(formatTime(0.0009999, locale)).toBe("999.9µs");
    expect(formatTime(59.999, locale)).toBe("60s"); // rounded by prettyNumber
    expect(formatTime(3599.999, locale)).toBe("59m 60s"); // rounded by prettyNumber
  });
});
