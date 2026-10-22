/* Copyright 2026 Marimo. All rights reserved. */

import NodeChildProcess from "node:child_process";
import NodeFs from "node:fs";
import NodePath from "node:path";
import NodeUrl from "node:url";
import { expect, it } from "vitest";

it("generates a stable protocol that tolerates experimental stream events", () => {
  const root = NodeUrl.fileURLToPath(new URL("../../", import.meta.url));
  // Keep the temporary bindings in the package so Node can resolve zod.
  const output = NodeFs.mkdtempSync(NodePath.join(root, ".protocol-test-"));
  try {
    const command = [
      "--experimental-strip-types",
      NodePath.join(root, "scripts/generate-protocol.ts"),
      "--output-dir",
      output,
    ];
    NodeChildProcess.execFileSync("node", command, { stdio: "pipe" });
    NodeChildProcess.execFileSync("node", [...command, "--check"], {
      stdio: "pipe",
    });
    NodeFs.mkdirSync(NodePath.join(output, "transport"));
    for (const name of ["frame.ts", "stream.ts"]) {
      NodeFs.copyFileSync(
        NodePath.join(root, "src/transport", name),
        NodePath.join(output, "transport", name),
      );
    }
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
      assert.equal("Analysis" in Protocol, false);
      assert.equal(Protocol.ObjectType.options.includes("analysis"), false);
      const stream = new EventStream({}, Protocol.ObjectType.options);
      const received = [];
      stream.subscribe(event => received.push(event));
      stream.receive({ event: "analysis", data: {} });
      stream.receive({ event: "ready", id: "1", data: {} });
      stream.receive({ event: "analysis", id: "2", data: {} });
      assert.equal(stream.cursor, "2");
      assert.equal(stream.resume(), "2");
      stream.receive({ event: "analysis", id: "3", data: {} });
      stream.receive({ event: "ready", id: "3", data: {} });
      stream.receive({ event: "reset", data: {} });
      assert.equal(stream.cursor, null);
      assert.deepEqual(received, [
        { event: "ready", id: "1", data: {} },
        { event: "ready", id: "3", data: {} },
        { event: "reset", data: {} },
      ]);
      console.log("stable stream verified");
    `,
      ],
      { encoding: "utf8" },
    );
    expect(result.trim()).toBe("stable stream verified");
  } finally {
    NodeFs.rmSync(output, { recursive: true, force: true });
  }
}, 30_000);
