/* Copyright 2023 Marimo. All rights reserved. */
import { CompletionConfig } from "@/core/config/config-schema";
import { Facet } from "@codemirror/state";

export const completionConfigState = Facet.define<
  CompletionConfig,
  CompletionConfig
>({
  combine: (values) => values[0],
});
