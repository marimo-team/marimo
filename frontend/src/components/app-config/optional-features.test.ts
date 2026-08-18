/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import { isPackageRequirementInstalled } from "./optional-features";

describe("isPackageRequirementInstalled", () => {
  const installedPackages = [
    { name: "mcp", version: "2.0.0" },
    { name: "polars", version: "1.8.2" },
  ];

  it("requires the package to be installed", () => {
    expect(
      isPackageRequirementInstalled({ name: "missing" }, installedPackages),
    ).toBe(false);
  });

  it("accepts an installed package without a minimum version", () => {
    expect(
      isPackageRequirementInstalled({ name: "polars" }, installedPackages),
    ).toBe(true);
  });

  it("rejects an installed package below the minimum version", () => {
    expect(
      isPackageRequirementInstalled(
        { name: "mcp", minVersion: "2.1.0" },
        installedPackages,
      ),
    ).toBe(false);
  });

  it.each(["2.0.0rc1", "2.0.0.dev1", "2.0.0-beta1"])(
    "rejects the prerelease version %s",
    (version) => {
      expect(
        isPackageRequirementInstalled({ name: "mcp", minVersion: "2.0.0" }, [
          { name: "mcp", version },
        ]),
      ).toBe(false);
    },
  );

  it("accepts an installed package at or above the minimum version", () => {
    expect(
      isPackageRequirementInstalled(
        { name: "mcp", minVersion: "2.0.0" },
        installedPackages,
      ),
    ).toBe(true);
    expect(
      isPackageRequirementInstalled(
        { name: "mcp", minVersion: "1.9.0" },
        installedPackages,
      ),
    ).toBe(true);
  });

  it("normalizes extras in the requirement name", () => {
    expect(
      isPackageRequirementInstalled(
        { name: "polars[pyarrow]" },
        installedPackages,
      ),
    ).toBe(true);
  });
});
