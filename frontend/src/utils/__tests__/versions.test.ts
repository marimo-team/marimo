/* Copyright 2024 Marimo. All rights reserved. */
import { describe, it, expect } from "vitest";
import { semverSort } from "../versions";

describe("semverSort", () => {
  it("should sort versions correctly", () => {
    const versions = ["1.0.0", "1.0.1", "1.0.10", "1.0.2"];
    const sortedVersions = versions.sort(semverSort);
    expect(sortedVersions).toEqual(["1.0.0", "1.0.1", "1.0.2", "1.0.10"]);
  });

  it("should handle pre-release versions correctly", () => {
    const versions = ["1.0.0-alpha", "1.0.0", "1.0.0-beta", "1.0.0-rc.1"];
    const sortedVersions = versions.sort(semverSort);
    expect(sortedVersions).toEqual([
      "1.0.0-alpha",
      "1.0.0-beta",
      "1.0.0-rc.1",
      "1.0.0",
    ]);
  });

  it("should handle versions with different number of segments", () => {
    const versions = ["1.0", "1.0.0", "1.0.1", "1.0.10"];
    const sortedVersions = versions.sort(semverSort);
    expect(sortedVersions).toEqual(["1.0", "1.0.0", "1.0.1", "1.0.10"]);
  });

  it("should handle versions with build metadata correctly", () => {
    const versions = [
      "1.0.0+001",
      "1.0.0+20130313144700",
      "1.0.0+exp.sha.5114f85",
    ];
    const sortedVersions = versions.sort(semverSort);
    expect(sortedVersions).toEqual([
      "1.0.0+001",
      "1.0.0+20130313144700",
      "1.0.0+exp.sha.5114f85",
    ]);
  });
});
