/* Copyright 2024 Marimo. All rights reserved. */

export interface PythonCode {
  toCode(): string;
}

const INDENT = "    ";

function indent(code: string): string {
  return code
    .split("\n")
    .map((line) => INDENT + line)
    .join("\n");
}

function indentList(list: PythonCode[]): string {
  return `\n${indent(list.map(asString).join(",\n"))}\n`;
}

function asString(value: string | PythonCode): string {
  if (typeof value === "string") {
    return value;
  }
  return value.toCode();
}

export class Variable implements PythonCode {
  constructor(public name: string) {}

  toCode(): string {
    return this.name;
  }
}

interface LiteralOptions {
  objectAsFieldNames?: boolean;
  removeNull?: boolean;
  removeUndefined?: boolean;
}

export class Literal implements PythonCode {
  constructor(
    public value: unknown,
    public opts: LiteralOptions = {
      objectAsFieldNames: false,
      removeNull: false,
      removeUndefined: true,
    },
  ) {}

  toCode(): string {
    const EMPTY_VALUE = "";
    const { objectAsFieldNames, removeNull, removeUndefined } = this.opts;

    if (this.value === undefined) {
      if (removeUndefined) {
        return EMPTY_VALUE;
      }
      return "None";
    }
    if (this.value === null) {
      if (removeNull) {
        return EMPTY_VALUE;
      }
      return "None";
    }
    if (typeof this.value === "string") {
      return `'${this.value}'`;
    }
    if (typeof this.value === "boolean") {
      return this.value ? "True" : "False";
    }

    if (Array.isArray(this.value)) {
      if (this.value.length === 0) {
        return "[]";
      }
      return `[\n${indent(
        this.value
          .map((item) => new Literal(item).toCode())
          .filter((item) => item !== EMPTY_VALUE)
          .join(",\n"),
      )}\n]`;
    }

    if (typeof this.value === "object") {
      const entries = Object.entries(this.value as Record<string, unknown>);
      if (entries.length === 0) {
        return "{}";
      }

      const formatEntry = (key: string, value: unknown, separator: string) => {
        const code = new Literal(value).toCode();
        if (code === "") {
          return "";
        }
        // Quote keys when in dictionary mode (not objectAsFieldNames)
        const formattedKey = objectAsFieldNames ? key : `'${key}'`;
        return `${formattedKey}${separator}${code}`;
      };

      // When objectAsFieldNames is true, we use = as the separator (eg. field=value)
      // Otherwise, we use : (eg. field: value)
      const formattedEntries = entries
        .map(([key, value]) =>
          formatEntry(key, value, objectAsFieldNames ? "=" : ": "),
        )
        .filter(Boolean)
        .join(",\n");

      return objectAsFieldNames
        ? `\n${indent(formattedEntries)}\n`
        : `{\n${indent(formattedEntries)}\n}`;
    }
    return String(this.value);
  }
}

export class VariableDeclaration implements PythonCode {
  constructor(
    public name: string,
    public value: string | PythonCode,
  ) {}

  toCode(): string {
    const right = asString(this.value);
    if (right.includes("\n")) {
      return `${this.name} = (\n${indent(right)}\n)`;
    }
    return `${this.name} = ${right}`;
  }
}

export class FunctionArg implements PythonCode {
  constructor(
    public name: string,
    public value: string | PythonCode,
  ) {}

  toCode(): string {
    return `${this.name}=${asString(this.value)}`;
  }
}

export class FunctionCall implements PythonCode {
  private args: PythonCode[];

  constructor(
    public name: string,
    args: PythonCode[] | Record<string, PythonCode>,
    public multiLine = false,
  ) {
    this.args = objectToArgs(args);
  }

  toCode(): string {
    if (this.multiLine) {
      if (this.args.length === 0) {
        return `${this.name}()`;
      }
      if (this.args.length === 1) {
        return `${this.name}(${this.args[0].toCode()})`;
      }
      return `${this.name}(${indentList(this.args)})`;
    }
    return `${this.name}(${this.args.map(asString).join(", ")})`;
  }

  addArg(...args: PythonCode[]): FunctionCall {
    return new FunctionCall(this.name, [...this.args, ...args], this.multiLine);
  }

  chain(
    name: string,
    args: PythonCode[] | Record<string, PythonCode>,
  ): FunctionCall {
    args = objectToArgs(args);

    if (this.multiLine) {
      return new FunctionCall(
        `${this.toCode()}\n.${name}`,
        args,
        this.multiLine,
      );
    }
    const fullName = `${this.toCode()}.${name}`;
    return new FunctionCall(fullName, args, this.multiLine);
  }
}

function objectToArgs(
  obj: Record<string, PythonCode> | PythonCode[],
): PythonCode[] {
  if (Array.isArray(obj)) {
    return obj;
  }
  return Object.entries(obj).map(([key, value]) => new FunctionArg(key, value));
}

/**
 * Converts an array of objects to a PythonCode object.
 * If there is only one object, it returns the object as a function call.
 * If there are multiple objects, it returns the objects wrapped in a list.
 */
export function objectsToPythonCode(obj: object[], prefix: string): PythonCode {
  if (obj.length === 0) {
    return new Literal(obj);
  }

  const functionCalls = obj.map((o) => {
    const args = Object.fromEntries(
      Object.entries(o)
        .filter(([, value]) => value !== undefined)
        .map(([key, value]) => {
          return [key, new Literal(value)];
        }),
    );
    return new FunctionCall(prefix, args);
  });

  // If there's only one object, return it directly
  if (obj.length === 1) {
    return functionCalls[0];
  }

  // Otherwise, return a list of function calls
  return {
    toCode: () => `[${indentList(functionCalls)}]`,
  };
}
