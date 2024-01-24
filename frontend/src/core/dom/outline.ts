/* Copyright 2024 Marimo. All rights reserved. */

import { Logger } from "@/utils/Logger";
import { OutputMessage } from "../kernel/messages";
import { Outline } from "../cells/outline";

function getOutline(html: string): Outline {
  const items: Outline["items"] = [];

  const parser = new DOMParser();
  const document = parser.parseFromString(html, "text/html");

  const headings = document.querySelectorAll("h1, h2, h3");
  // eslint-disable-next-line unicorn/prefer-spread
  for (const heading of Array.from(headings)) {
    const name = heading.textContent;
    if (!name) {
      continue;
    }

    const id = heading.id;
    if (!id) {
      continue;
    }

    const level = Number.parseInt(heading.tagName[1], 10);
    items.push({ name, id, level });
  }

  return { items };
}

export function mergeOutlines(outlines: Array<Outline | null>): Outline {
  return {
    items: outlines.filter(Boolean).flatMap((outline) => outline.items),
  };
}

export function parseOutline(output: OutputMessage | null): Outline | null {
  if (output == null) {
    return null;
  }

  if (output.mimetype !== "text/html") {
    return null;
  }

  try {
    return getOutline(output.data);
  } catch {
    Logger.error("Failed to parse outline");
    return null;
  }
}
