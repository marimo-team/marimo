/* Copyright 2023 Marimo. All rights reserved. */
import { ZodType, ZodTypeDef } from "zod";

/**
 * State setter. Either a value or a function that takes the previous value and
 * returns the new value.
 */
export type Setter<S> = (value: S | ((prev: S) => S)) => void;

/**
 * Props for a plugin.
 *
 * TODO(akshayka): (Maybe) add children elements for composition
 */
export interface IPluginProps<S, D> {
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
export interface IPlugin<S, D = Record<string, never>> {
  /**
   * The html tag name to render the plugin.
   */
  tagName: string;

  /**
   * Validate the plugin data. Use [zod](https://zod.dev/) to validate the data.
   */
  validator: ZodType<D, ZodTypeDef, unknown>;

  /**
   * Render the plugin.
   */
  render(props: IPluginProps<S, D>): JSX.Element;
}
