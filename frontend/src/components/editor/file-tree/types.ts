/* Copyright 2026 Marimo. All rights reserved. */

import type { FileIconType } from "@/components/ui/file-icons";

const TAB = "    ";

export const PYTHON_CODE_FOR_FILE_TYPE: Record<
  FileIconType,
  (path: string) => string
> = {
  directory: (path) => `os.listdir("${path}")`,
  python: (path) => `with open("${path}", "r") as _f:\n${TAB}...\n`,
  json: (path) =>
    `with open("${path}", "r") as _f:\n${TAB}_data = json.load(_f)\n`,
  code: (path) => `with open("${path}", "r") as _f:\n${TAB}...\n`,
  text: (path) => `with open("${path}", "r") as _f:\n${TAB}...\n`,
  image: (path) => `mo.image("${path}")`,
  audio: (path) => `mo.audio("${path}")`,
  video: (path) => `mo.video("${path}")`,
  pdf: (path) => `with open("${path}", "rb") as _f:\n${TAB}...\n`,
  zip: (path) => `with open("${path}", "rb") as _f:\n${TAB}...\n`,
  data: (path) => `with open("${path}", "r") as _f:\n${TAB}...\n`,
  unknown: (path) => `with open("${path}", "r") as _f:\n${TAB}...\n`,
};
