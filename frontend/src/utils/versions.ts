/* Copyright 2024 Marimo. All rights reserved. */

export function semverSort(a: string, b: string) {
  const semverRegex = /^(\d+)\.(\d+)\.(\d+)(?:-([\w.-]+))?(?:\+([\w.-]+))?$/;

  const parseSemver = (version: string) => {
    const match = semverRegex.exec(version);
    if (!match) {
      return null;
    }

    const [, major, minor, patch, preRelease] = match;
    return {
      major: Number.parseInt(major, 10),
      minor: Number.parseInt(minor, 10),
      patch: Number.parseInt(patch, 10),
      preRelease: preRelease || "",
    };
  };

  try {
    const aParsed = parseSemver(a);
    const bParsed = parseSemver(b);

    if (!aParsed || !bParsed) {
      return a.localeCompare(b, undefined, {
        numeric: true,
        sensitivity: "base",
      });
    }

    if (aParsed.major !== bParsed.major) {
      return aParsed.major - bParsed.major;
    }
    if (aParsed.minor !== bParsed.minor) {
      return aParsed.minor - bParsed.minor;
    }
    if (aParsed.patch !== bParsed.patch) {
      return aParsed.patch - bParsed.patch;
    }

    if (aParsed.preRelease === "" && bParsed.preRelease !== "") {
      return 1;
    }
    if (aParsed.preRelease !== "" && bParsed.preRelease === "") {
      return -1;
    }

    return aParsed.preRelease.localeCompare(bParsed.preRelease);
  } catch {
    return a.localeCompare(b, undefined, {
      numeric: true,
      sensitivity: "base",
    });
  }
}

export const reverseSemverSort = (a: string, b: string) => semverSort(b, a);

/**
 * Remove any `[` and `]` characters from the module name. For example:
 * `ibis-framework[duckdb]` -> `ibis-framework`
 */
export function cleanPythonModuleName(name: string) {
  return name.replaceAll(/\[.*]/g, "").trim();
}
