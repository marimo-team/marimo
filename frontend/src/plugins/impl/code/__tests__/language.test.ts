/* Copyright 2026 Marimo. All rights reserved. */

import { langs } from "@uiw/codemirror-extensions-langs";
import { describe, expect, it } from "vitest";
import { LANGUAGE_MAP } from "../any-language-editor";

describe("Codemirror Languages", () => {
  const codemirrorLanguages = Object.keys(langs);

  it("LANGUAGE_MAP should have all the languages in CodeMirror", () => {
    for (const language of Object.values(LANGUAGE_MAP)) {
      expect(codemirrorLanguages).toContain(language);
    }
  });
});
