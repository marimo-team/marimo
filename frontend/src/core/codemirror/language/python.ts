/* Copyright 2023 Marimo. All rights reserved. */
import { Extension } from "@codemirror/state";
import { LanguageAdapter } from "./types";
import {
  pythonLanguage,
  localCompletionSource,
  globalCompletion,
} from "@codemirror/lang-python";
import {
  foldNodeProp,
  foldInside,
  LanguageSupport,
} from "@codemirror/language";

/**
 * Language adapter for Python.
 */
export class PythonLanguageAdapter implements LanguageAdapter {
  type = "python";

  transformIn(code: string): [string, number] {
    return [code, 0];
  }

  transformOut(code: string): [string, number] {
    return [code, 0];
  }

  isSupported(_code: string): boolean {
    return true;
  }

  getExtension(): Extension {
    return [
      new LanguageSupport(customizedPython, [
        customizedPython.data.of({ autocomplete: localCompletionSource }),
        customizedPython.data.of({ autocomplete: globalCompletion }),
      ]),
    ];
  }
}

// Customize python to support folding some additional syntax nodes
const customizedPython = pythonLanguage.configure({
  props: [
    foldNodeProp.add({
      ParenthesizedExpression: foldInside,
      // Fold function calls whose arguments are split over multiple lines
      ArgList: foldInside,
    }),
  ],
});
