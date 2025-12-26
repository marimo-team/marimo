/* Copyright 2026 Marimo. All rights reserved. */
import { lazy } from "react";

export const LazyAnyLanguageCodeMirror = lazy(
  () => import("./any-language-editor"),
);
