/* Copyright 2024 Marimo. All rights reserved. */
import { lazy } from "react";

export const LazyAnyLanguageCodeMirror = lazy(
  () => import("./any-language-editor"),
);
