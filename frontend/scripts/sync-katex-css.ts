/* Copyright 2026 Marimo. All rights reserved. */

import { writeFile } from "node:fs/promises";
import {
  generateKatexCss,
  readUpstreamCss,
  stylesheetPath,
} from "./katex-css.ts";

await writeFile(
  stylesheetPath,
  await generateKatexCss(await readUpstreamCss()),
);
process.stdout.write(
  "Regenerated frontend/src/css/katex.min.css. Review the diff and run pnpm --dir frontend test src/css/katex-css.test.ts.\n",
);
