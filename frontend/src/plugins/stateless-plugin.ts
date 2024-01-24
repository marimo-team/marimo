/* Copyright 2024 Marimo. All rights reserved. */
import { IPlugin } from "./types";

export interface IStatelessPluginProps<D> {
  /**
   * Host element.
   */
  host: HTMLElement;

  /**
   * Plugin data.
   */
  data: D;

  /**
   * Children elements.
   */
  children?: React.ReactNode | undefined;
}

export interface IStatelessPlugin<D>
  extends Omit<IPlugin<never, D>, "render" | "functions"> {
  /**
   * Render the plugin.
   */
  render(props: IStatelessPluginProps<D>): JSX.Element;
}
