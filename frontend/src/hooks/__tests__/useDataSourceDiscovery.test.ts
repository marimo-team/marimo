/* Copyright 2026 Marimo. All rights reserved. */

import { afterEach, describe, expect, it, vi } from "vitest";
import { DiscoverDataSources } from "@/core/datasets/request-registry";
import { loadDataSourceDiscovery } from "../useDataSourceDiscovery";

describe("loadDataSourceDiscovery", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("returns the kernel's secret-free discovery model", async () => {
    const sources = [
      {
        id: "pyiceberg-prod",
        integration: "pyiceberg",
        category: "catalog" as const,
        displayName: "PyIceberg (prod)",
        confidence: "high" as const,
        origins: [
          {
            type: "configuration" as const,
            label: "Resolved PyIceberg configuration",
          },
        ],
        configuration: [
          {
            field: "Catalog",
            value: {
              kind: "safe-literal" as const,
              value: "prod",
            },
          },
        ],
        code: 'catalog = load_catalog("prod")',
      },
    ];
    const request = vi.spyOn(DiscoverDataSources, "request").mockResolvedValue({
      request_id: "request-id",
      sources,
    });

    const detected = await loadDataSourceDiscovery();

    expect({ detected, requests: request.mock.calls }).toMatchInlineSnapshot(`
      {
        "detected": [
          {
            "category": "catalog",
            "code": "catalog = load_catalog("prod")",
            "confidence": "high",
            "configuration": [
              {
                "field": "Catalog",
                "value": {
                  "kind": "safe-literal",
                  "value": "prod",
                },
              },
            ],
            "displayName": "PyIceberg (prod)",
            "id": "pyiceberg-prod",
            "integration": "pyiceberg",
            "origins": [
              {
                "label": "Resolved PyIceberg configuration",
                "type": "configuration",
              },
            ],
          },
        ],
        "requests": [
          [
            {},
          ],
        ],
      }
    `);
  });
});
