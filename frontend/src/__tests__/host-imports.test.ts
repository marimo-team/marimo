/* Copyright 2026 Marimo. All rights reserved. */

import NodeChildProcess from "node:child_process";
import NodeFs from "node:fs";
import NodeOs from "node:os";
import NodePath from "node:path";
import NodeUrl from "node:url";
import { expect, it } from "vitest";
import { z } from "zod";

it("enforces host dependencies and the single native notification type exception", () => {
  const frontend = NodeUrl.fileURLToPath(
    new NodeUrl.URL("../../", import.meta.url),
  );
  const directory = NodeFs.mkdtempSync(
    NodePath.join(NodeOs.tmpdir(), "host-imports-"),
  );
  const files = {
    "src/core/host/allowed.ts": `
      import { atom } from "jotai/vanilla";
      import { z } from "zod";
      import { Logger } from "@/utils/Logger";
      import type { Document } from "./document";
      export * from "@/core/host/events";
      type Event = import("./events").NotebookEvent;
      void import("./protocol");
    `,
    "src/core/host/protocol.ts": `
      import type { NotificationMessage as A } from "../kernel/messages";
      import { type NotificationMessage as B } from "@/core/kernel/messages";
      import { NotificationMessage as C } from "../kernel/messages";
      import type { NotificationPayload } from "../kernel/messages";
    `,
    "src/core/host/forbidden.ts": `
      import { useEffect } from "react";
      import type { NotificationMessage } from "../kernel/messages";
      export * from "../kernel/messages";
      export { Logger } from "@/utils/Logger/../other";
      void import("../kernel/messages");
      type Message = import("../kernel/messages").NotificationMessage;
      const module = require("../kernel/messages");
      void import(module);
    `,
    "src/core/host/__tests__/allowed.ts": `import { useEffect } from "react";`,
    "src/core/websocket/allowed.ts": `import { useEffect } from "react";`,
  };
  try {
    for (const [path, source] of Object.entries(files)) {
      const destination = NodePath.join(directory, path);
      NodeFs.mkdirSync(NodePath.dirname(destination), { recursive: true });
      NodeFs.writeFileSync(destination, source);
    }
    const result = NodeChildProcess.spawnSync(
      NodePath.join(frontend, "node_modules/.bin/oxlint"),
      [
        "--config",
        NodePath.join(frontend, ".oxlintrc.json"),
        "--format",
        "json",
        directory,
      ],
      { cwd: frontend, encoding: "utf8" },
    );
    const report = z
      .object({
        diagnostics: z.array(
          z.object({
            severity: z.string(),
            filename: z.string(),
            labels: z.array(z.object({ span: z.object({ line: z.number() }) })),
          }),
        ),
      })
      .parse(JSON.parse(result.stdout));
    const errors = report.diagnostics.filter(
      (diagnostic) => diagnostic.severity === "error",
    );
    expect(
      errors
        .map((error) => ({
          file: NodePath.basename(error.filename),
          line: error.labels[0].span.line,
        }))
        .toSorted((a, b) => a.file.localeCompare(b.file) || a.line - b.line),
    ).toEqual([
      ...[2, 3, 4, 5, 6, 7, 8, 9].map((line) => ({
        file: "forbidden.ts",
        line,
      })),
      { file: "protocol.ts", line: 4 },
      { file: "protocol.ts", line: 5 },
    ]);
    expect(result.status).toBe(1);
  } finally {
    NodeFs.rmSync(directory, { recursive: true, force: true });
  }
});
