/* Copyright 2024 Marimo. All rights reserved. */
import { ZodType, ZodTypeDef } from "zod";
import { IPluginProps, IPlugin } from "../types";
import { FunctionSchemas, PluginFunctions } from "./rpc";

type Renderer<S, D, F> = (props: IPluginProps<S, D, F>) => JSX.Element;
// If this simple builder pattern becomes unwieldy, we can switch to a more
// complex builder pattern with individual classes.

export function createPlugin<S>(tagName: string) {
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
            tagName,
            validator,
            render: renderer,
          };
        },
      };
    },
  };
}
