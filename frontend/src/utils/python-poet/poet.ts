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
  removeNull?: boolean;
  removeUndefined?: boolean;
}

export class Literal implements PythonCode {
  constructor(
    public readonly value: unknown,
    public readonly opts: LiteralOptions = {},
  ) {}

  static from(value: unknown, opts: LiteralOptions = {}): Literal {
    return new Literal(value, opts);
  }

  toCode(): string {
    const EMPTY_VALUE = "";
    const { removeNull = false, removeUndefined = true } = this.opts;

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

    // If a PythonCode object
    if (typeof this.value === "object" && "toCode" in this.value) {
      return (this.value as PythonCode).toCode();
    }

    if (Array.isArray(this.value)) {
      if (this.value.length === 0) {
        return "[]";
      }
      return `[\n${indent(
        this.value
          .map((item) => new Literal(item, this.opts).toCode())
          .filter((item) => item !== EMPTY_VALUE)
          .join(",\n"),
      )}\n]`;
    }

    if (typeof this.value === "object") {
      const entries = Object.entries(this.value as Record<string, unknown>);
      if (entries.length === 0) {
        return "{}";
      }

      const formatEntry = (entry: [string, unknown]) => {
        const [key, value] = entry;
        const code = new Literal(value, this.opts).toCode();
        if (code === "") {
          return "";
        }
        return `'${key}': ${code}`;
      };

      const formattedEntries = entries
        .map(formatEntry)
        .filter(Boolean)
        .join(",\n");

      return `{\n${indent(formattedEntries)}\n}`;
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

    // If the function call is multi-line, we need to add a newline to the name
    const fullName = this.multiLine
      ? `${this.toCode()}\n.${name}`
      : `${this.toCode()}.${name}`;

    return new FunctionCall(fullName, args, this.multiLine);
  }
}

function objectToArgs(
  obj: Record<string, PythonCode> | PythonCode[],
): PythonCode[] {
  if (Array.isArray(obj)) {
    return obj;
  }
  const entries = Object.entries(obj);
  if (entries.length === 0) {
    return [];
  }
  return entries.map(([key, value]) => new FunctionArg(key, value));
}
