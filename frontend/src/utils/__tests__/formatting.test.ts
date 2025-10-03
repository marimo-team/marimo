/* Copyright 2024 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import { formatBytes, formatTime } from "../formatting";

describe("formatBytes", () => {
  it("should format 0 bytes", () => {
    expect(formatBytes(0)).toBe("0 B");
    expect(formatBytes(-1)).toBe("0 B");
  });

  it("should format bytes", () => {
    expect(formatBytes(100)).toBe("100 B");
    expect(formatBytes(512)).toBe("512 B");
    expect(formatBytes(1023)).toBe("1,023 B");
  });

  it("should format kilobytes", () => {
    expect(formatBytes(1024)).toBe("1 KB");
    expect(formatBytes(1536)).toBe("1.5 KB");
    expect(formatBytes(10240)).toBe("10 KB");
  });

  it("should format megabytes", () => {
    expect(formatBytes(1048576)).toBe("1 MB"); // 1024^2
    expect(formatBytes(1572864)).toBe("1.5 MB"); // 1.5 * 1024^2
    expect(formatBytes(10485760)).toBe("10 MB");
  });

  it("should format gigabytes", () => {
    expect(formatBytes(1073741824)).toBe("1 GB"); // 1024^3
    expect(formatBytes(1610612736)).toBe("1.5 GB"); // 1.5 * 1024^3
    expect(formatBytes(10737418240)).toBe("10 GB");
  });

  it("should format terabytes", () => {
    expect(formatBytes(1099511627776)).toBe("1 TB"); // 1024^4
    expect(formatBytes(1649267441664)).toBe("1.5 TB"); // 1.5 * 1024^4
  });

  it("should respect locale parameter", () => {
    // German locale uses different separators
    const bytes = 1536; // 1.5 KB
    expect(formatBytes(bytes, "de-DE")).toContain("1,5");
    // US locale uses dot
    expect(formatBytes(bytes, "en-US")).toContain("1.5");
  });
});

describe("formatTime", () => {
  it("should format 0 seconds", () => {
    expect(formatTime(0)).toBe("0s");
  });

  it("should format microseconds", () => {
    expect(formatTime(0.0000001)).toBe("0.1µs");
    expect(formatTime(0.0000005)).toBe("0.5µs");
    expect(formatTime(0.000000999)).toBe("1µs"); // rounded by prettyNumber
  });

  it("should format milliseconds", () => {
    expect(formatTime(0.001)).toBe("1ms");
    expect(formatTime(0.0015)).toBe("1.5ms");
    expect(formatTime(0.1)).toBe("100ms");
    expect(formatTime(0.5)).toBe("500ms");
    expect(formatTime(0.999)).toBe("999ms");
  });

  it("should format seconds", () => {
    expect(formatTime(1)).toBe("1s");
    expect(formatTime(1.5)).toBe("1.5s");
    expect(formatTime(30)).toBe("30s");
    expect(formatTime(59.9)).toBe("59.9s");
  });

  it("should format minutes and seconds", () => {
    expect(formatTime(60)).toBe("1m");
    expect(formatTime(90)).toBe("1m 30s");
    expect(formatTime(150)).toBe("2m 30s");
    expect(formatTime(3540)).toBe("59m");
    expect(formatTime(3599)).toBe("59m 59s");
  });

  it("should format hours and minutes", () => {
    expect(formatTime(3600)).toBe("1h");
    expect(formatTime(3660)).toBe("1h 1m");
    expect(formatTime(5400)).toBe("1h 30m");
    expect(formatTime(7200)).toBe("2h");
    expect(formatTime(9000)).toBe("2h 30m");
  });

  it("should respect locale parameter", () => {
    // German locale uses comma for decimal separator
    const time = 1.5;
    expect(formatTime(time, "de-DE")).toContain("1,5");
    // US locale uses dot
    expect(formatTime(time, "en-US")).toContain("1.5");
  });

  it("should handle edge cases", () => {
    expect(formatTime(0.0009999)).toBe("999.9µs");
    expect(formatTime(59.999)).toBe("60s"); // rounded by prettyNumber
    expect(formatTime(3599.999)).toBe("59m 60s"); // rounded by prettyNumber
  });
});
