/* Copyright 2024 Marimo. All rights reserved. */
import { describe, it, beforeAll, afterEach, afterAll, expect } from "vitest";
import * as msw from "msw";
import { setupServer } from "msw/node";
import { renderHook, waitFor } from "@testing-library/react";

import {
  usePackageMetadata,
  type PyPiPackageResponse,
} from "../usePackageMetadata";

function createPackageMock(options: {
  extras?: string[] | null;
  versions: string[];
}): PyPiPackageResponse {
  return {
    info: {
      provides_extra: options.extras ?? null,
    },
    releases: Object.fromEntries(options.versions.map((v) => [v, []])),
  };
}

// https://mswjs.io/docs/api/setup-server/#usage
const server = setupServer();

beforeAll(() => {
  // Start the interception.
  server.listen();
});

afterEach(() => {
  // Remove any handlers you may have added in individual tests (runtime handlers).
  server.resetHandlers();
});

afterAll(() => {
  // Disable request interception and clean up.
  server.close();
});

describe("usePackageMetadata", () => {
  it("should return loading state initially", async () => {
    server.use(
      msw.http.get("https://pypi.org/pypi/numpy/json", async () => {
        msw.delay();
        return msw.HttpResponse.json(
          createPackageMock({
            extras: ["test", "dev"],
            versions: ["1.21.0", "1.20.0"],
          }),
        );
      }),
    );
    const { result } = renderHook(() => usePackageMetadata("numpy"));
    expect(result.current.loading).toBe(true);
    expect(result.current.data).toBeUndefined();
    expect(result.current.error).toBeUndefined();
  });

  it("should fetch and return package metadata successfully", async () => {
    server.use(
      msw.http.get("https://pypi.org/pypi/pandas/json", () => {
        return msw.HttpResponse.json(
          createPackageMock({
            extras: ["test", "performance", "plotting"],
            versions: ["2.0.0", "1.5.3", "1.4.0"],
          }),
        );
      }),
    );

    const { result } = renderHook(() => usePackageMetadata("pandas"));

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.data).toEqual({
      versions: ["2.0.0", "1.5.3", "1.4.0"],
      extras: ["test", "performance", "plotting"],
    });
    expect(result.current.error).toBeUndefined();
  });

  it("should handle packages with no extras", async () => {
    server.use(
      msw.http.get("https://pypi.org/pypi/requests/json", () =>
        msw.HttpResponse.json(
          createPackageMock({
            extras: null,
            versions: ["2.28.0", "2.27.1"],
          }),
        ),
      ),
    );

    const { result } = renderHook(() => usePackageMetadata("requests"));
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.data).toEqual({
      versions: ["2.28.0", "2.27.1"],
      extras: [],
    });
    expect(result.current.error).toBeUndefined();
  });

  it("should handle network errors", async () => {
    server.use(
      msw.http.get("https://pypi.org/pypi/nonexistent/json", () =>
        msw.HttpResponse.error(),
      ),
    );

    const { result } = renderHook(() => usePackageMetadata("nonexistent"));
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.data).toBeUndefined();
    expect(result.current.error).toBeInstanceOf(Error);
  });

  it("should clean package names with extras syntax", async () => {
    server.use(
      msw.http.get("https://pypi.org/pypi/package-name/json", () =>
        msw.HttpResponse.json(
          createPackageMock({
            extras: ["extra1", "extra2"],
            versions: ["1.0.0"],
          }),
        ),
      ),
    );

    const { result } = renderHook(() =>
      usePackageMetadata("package-name[extra1,extra2]"),
    );
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.data).toEqual({
      versions: ["1.0.0"],
      extras: ["extra1", "extra2"],
    });
  });

  it("should sort versions in reverse semver order", async () => {
    server.use(
      msw.http.get("https://pypi.org/pypi/scipy/json", () =>
        msw.HttpResponse.json(
          createPackageMock({
            extras: [],
            versions: ["1.9.0", "1.10.1", "1.8.1", "2.0.0"],
          }),
        ),
      ),
    );

    const { result } = renderHook(() => usePackageMetadata("scipy"));
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.data).toMatchInlineSnapshot(`
      {
        "extras": [],
        "versions": [
          "2.0.0",
          "1.10.1",
          "1.9.0",
          "1.8.1",
        ],
      }
    `);
  });

  it("should handle 404 package not found error", async () => {
    server.use(
      msw.http.get(
        "https://pypi.org/pypi/package-not-found/json",
        () => new msw.HttpResponse(null, { status: 404 }),
      ),
    );

    const { result } = renderHook(() =>
      usePackageMetadata("package-not-found"),
    );
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.data).toBeUndefined();
    expect(result.current.error).toBeInstanceOf(Error);
  });

  it("should use cached data on subsequent calls", async () => {
    let callCount = 0;
    server.use(
      msw.http.get("https://pypi.org/pypi/cached-package/json", () => {
        callCount++;
        return msw.HttpResponse.json(
          createPackageMock({
            extras: ["test"],
            versions: ["1.0.0"],
          }),
        );
      }),
    );

    // First
    const { result: result1 } = renderHook(() =>
      usePackageMetadata("cached-package"),
    );

    await waitFor(() => expect(result1.current.loading).toBe(false));
    expect(result1.current.data).toEqual({
      versions: ["1.0.0"],
      extras: ["test"],
    });
    expect(callCount).toBe(1);

    // Second
    const { result: result2 } = renderHook(() =>
      usePackageMetadata("cached-package"),
    );
    await waitFor(() => expect(result2.current.loading).toBe(false));
    expect(result2.current.data).toEqual({
      versions: ["1.0.0"],
      extras: ["test"],
    });
    expect(callCount).toBe(1);
  });
});
