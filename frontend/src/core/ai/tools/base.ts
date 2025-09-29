/* Copyright 2024 Marimo. All rights reserved. */

import type { AnyZodObject, z } from "zod";

/**
 * Minimal base class for frontend tools.
 *
 * Structural typing ensures instances are compatible with the Tool<TIn, TOut>
 * interface used by the registry, without importing it here.
 */
export abstract class BaseTool<
  TIn extends AnyZodObject,
  TOut extends AnyZodObject,
> {
  public readonly name: string;
  public readonly description: string;
  public readonly schema: TIn;
  public readonly outputSchema: TOut;
  public readonly mode: ("manual" | "ask")[];

  /**
   * Handler exposed to the registry. Calls the subclass implementation.
   */
  public readonly handler: (args: z.infer<TIn>) => z.infer<TOut> | Promise<z.infer<TOut>>;

  constructor(options: {
    name: string;
    description: string;
    schema: TIn;
    mode: ("manual" | "ask")[];
    outputSchema: TOut;
  }) {
    this.name = options.name;
    this.description = options.description;
    this.schema = options.schema;
    this.mode = options.mode;
    this.outputSchema = options.outputSchema;
    this.handler = (args) => Promise.resolve(this.handle(args));
  }

  /** Implement tool logic in subclasses */
  protected abstract handle(args: z.infer<TIn>): z.infer<TOut> | Promise<z.infer<TOut>>;
}


