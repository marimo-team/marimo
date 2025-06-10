/* Copyright 2024 Marimo. All rights reserved. */
import type { ZodType, ZodTypeDef } from "zod";
import type { IPluginProps, IPlugin } from "../types";
import type { FunctionSchemas, PluginFunctions } from "./rpc";

import type { JSX } from "react";

type Renderer<S, D, F> = (props: IPluginProps<S, D, F>) => JSX.Element;
// If this simple builder pattern becomes unwieldy, we can switch to a more
// complex builder pattern with individual classes.

export function createPlugin<S>(
  tagName: string,
  opts: {
    cssStyles?: string[];
  } = {},
) {
  return {
    /**
     * Data schema for the plugin.
     */
    withData<D>(validator: ZodType<D, ZodTypeDef, unknown>) {
      return {
        /**
         * Functions that the plugin can call.
         */
        withFunctions<F extends PluginFunctions>(
          functions: FunctionSchemas<F>,
        ) {
          return {
            /**
             * Render the plugin.
             */
            renderer(renderer: Renderer<S, D, F>): IPlugin<S, D, F> {
              return {
                ...opts,
                tagName,
                validator,
                functions,
                render: renderer,
              };
            },
          };
        },
        /**
         * Render the plugin.
         */
        renderer(renderer: Renderer<S, D, unknown>): IPlugin<S, D> {
          return {
            ...opts,
            tagName,
            validator,
            render: renderer,
          };
        },
      };
    },
  };
}
