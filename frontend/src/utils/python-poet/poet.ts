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

export class Literal implements PythonCode {
  constructor(public value: unknown) {}

  toCode(): string {
    if (typeof this.value === "string") {
      return `'${this.value}'`;
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
      return `${this.name}(\n${indent(this.args.map(asString).join(",\n"))}\n)`;
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
