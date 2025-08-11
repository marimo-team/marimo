interface Body {
  json<T = unknown>(): Promise<T>;
}

interface JSON {
  parse(
    text: string,
    reviver?: (this: any, key: string, value: any) => any,
  ): unknown;
}

interface Array<T> {
  filter(predicate: BooleanConstructor): Array<NonNullable<T>>;
}

interface String {
  /**
   * Split a string into substrings using the specified separator and return them as an array.
   * @param splitter An object that can split a string.
   * @param limit A value used to limit the number of elements returned in the array.
   */
  split<T extends string | undefined = string | undefined>(
    splitter: { [Symbol.split](string: string, limit?: number): string[] },
    limit?: number,
  ): T[];
  split<T extends string | undefined = string | undefined>(
    splitter: string,
    limit?: number,
  ): T[];
}
