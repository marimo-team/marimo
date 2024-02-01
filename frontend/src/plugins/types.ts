/* Copyright 2024 Marimo. All rights reserved. */
import { ZodType, ZodTypeDef } from "zod";
import { PluginFunctions, FunctionSchemas } from "./core/rpc";

/**
 * State setter. Either a value or a function that takes the previous value and
 * returns the new value.
 */
export type Setter<S> = (value: S | ((prev: S) => S)) => void;

/**
 * Props for a plugin.
 */
export interface IPluginProps<S, D, F = {}> {
  /**
   * Host element.
   */
  host: HTMLElement;
  /**
   * The state of the plugin.
   */
  value: S;
  /**
   * Set the state of the plugin.
   */
  setValue: Setter<S>;
  /**
   * Plugin data.
   */
  data: D;

  /**
   * Functions that can be called from the plugin.
   */
  functions: F;

  /**
   * Children elements.
   */
  children?: React.ReactNode | undefined;
}

/**
 * Map of plugin data to stringified value.
 */
export type StringifiedPluginData<D> = {
  [K in keyof D]: string;
};

/**
 * A plugin.
 * @template S - the type of the state
 * @template P - the type of the props
 */
export interface IPlugin<
  S,
  D = Record<string, never>,
  F extends PluginFunctions = {},
> {
  /**
   * The html tag name to render the plugin.
   */
  tagName: string;

  /**
   * Validate the plugin data. Use [zod](https://zod.dev/) to validate the data.
   */
  validator: ZodType<D, ZodTypeDef, unknown>;

  /**
   * Functions definitions and validation.
   */
  functions?: FunctionSchemas<F>;

  /**
   * Render the plugin.
   */
  render(props: IPluginProps<S, D, F>): JSX.Element;
}
