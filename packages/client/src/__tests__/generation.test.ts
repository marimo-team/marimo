/* Copyright 2026 Marimo. All rights reserved. */

import NodeChildProcess from "node:child_process";
import NodeFs from "node:fs";
import NodePath from "node:path";
import NodeUrl from "node:url";
import { expect, it } from "vitest";

it.each(["stable", "catalog feature"] as const)(
  "delivers the generated %s stream kinds",
  (selection) => {
    const root = NodeUrl.fileURLToPath(new URL("../../", import.meta.url));
    // Keep the temporary bindings in the package so Node can resolve zod.
    const project = NodeFs.mkdtempSync(NodePath.join(root, ".protocol-test-"));
    const output = NodePath.join(project, "src");
    try {
      NodeFs.cpSync(NodePath.join(root, "src"), output, { recursive: true });
      const command = [
        "--experimental-strip-types",
        NodePath.join(root, "scripts/generate-protocol.ts"),
        "--output-dir",
        output,
      ];
      const host = NodePath.join(root, "../host-protocol");
      const input =
        selection === "stable"
          ? NodeChildProcess.execFileSync("node", ["scripts/openapi.ts"], {
              cwd: host,
            })
          : NodeChildProcess.execFileSync(
              "node",
              [
                "--input-type=module",
                "-e",
                `
        import { Schema } from "effect";
        import { OpenApi } from "effect/http-api";
        import { makeHostContract } from "./src/contract.ts";
        import { defineFeature } from "./src/experimental/defineFeature.ts";
        import { features } from "./src/experimental/index.ts";
        import { referencePolicy } from "./src/Host.ts";
        const badge = Schema.Struct({ label: Schema.String }).annotate({ identifier: "Badge" });
        const feature = defineFeature({ objects: [{ kind: "badge", schema: badge, streams: ["catalog"], removable: false }] });
        console.log(JSON.stringify(OpenApi.fromApi(makeHostContract([...features, feature]).Api, { referencePolicy })));
      `,
              ],
              { cwd: host },
            );
      NodeChildProcess.execFileSync("node", command, { input, stdio: "pipe" });
      NodeChildProcess.execFileSync("node", [...command, "--check"], {
        input,
        stdio: "pipe",
      });
      if (selection === "catalog feature") {
        NodeFs.copyFileSync(
          NodePath.join(root, "tsconfig.json"),
          NodePath.join(project, "tsconfig.json"),
        );
        NodeChildProcess.execFileSync(
          "node",
          [
            NodePath.join(root, "node_modules/typescript/bin/tsc"),
            "-p",
            project,
          ],
          { stdio: "pipe" },
        );
      }
      const kinds = NodeUrl.pathToFileURL(
        NodePath.join(output, "kinds.ts"),
      ).href;
      const protocol = NodeUrl.pathToFileURL(
        NodePath.join(output, "protocol.ts"),
      ).href;
      const stream = NodeUrl.pathToFileURL(
        NodePath.join(output, "transport/stream.ts"),
      ).href;
      const result = NodeChildProcess.execFileSync(
        "node",
        [
          "--experimental-strip-types",
          "--input-type=module",
          "-e",
          `
      import assert from "node:assert/strict";
      import * as Protocol from ${JSON.stringify(protocol)};
      import { EventStream } from ${JSON.stringify(stream)};
      assert.equal("Analysis" in Protocol, ${selection === "catalog feature"});
      assert.equal(Protocol.ObjectKind.options.includes("analysis"), ${selection === "catalog feature"});
      const { catalogKinds, notebookKinds } = await import(${JSON.stringify(kinds)});
      const catalog = new EventStream({}, catalogKinds);
      const catalogEvents = [];
      catalog.subscribe(event => catalogEvents.push(event.event));
      const stream = new EventStream({}, notebookKinds);
      const received = [];
      stream.subscribe(event => received.push(event));
      const badge = { event: "badge", data: { badge: { label: "new" } } };
      catalog.receive(badge);
      stream.receive(badge);
      assert.deepEqual(catalogEvents, ${selection === "stable" ? "[]" : '["badge"]'});
      assert.deepEqual(received, []);
      const unknown = ${selection === "stable" ? '"analysis"' : '"future"'};
      stream.receive({ event: unknown, data: {} });
      stream.receive({ event: "ready", id: "1", data: {} });
      stream.receive({ event: unknown, id: "2", data: {} });
      assert.equal(stream.cursor, "2");
      assert.equal(stream.resume(), "2");
      stream.receive({ event: unknown, id: "3", data: {} });
      stream.receive({ event: "ready", id: "3", data: {} });
      stream.receive({ event: "reset", data: {} });
      assert.equal(stream.cursor, null);
      assert.deepEqual(received, [
        { event: "ready", id: "1", data: {} },
        { event: "ready", id: "3", data: {} },
        { event: "reset", data: {} },
      ]);
      console.log("stream kinds verified");
    `,
        ],
        { encoding: "utf8" },
      );
      expect(result.trim()).toBe("stream kinds verified");
    } finally {
      NodeFs.rmSync(project, { recursive: true, force: true });
    }
  },
  30_000,
);
