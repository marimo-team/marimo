/* Copyright 2024 Marimo. All rights reserved. */

export class PluralWord {
  public singular: string;
  public _plural?: string;

  constructor(singular: string, _plural?: string) {
    this.singular = singular;
    this._plural = _plural;
  }

  public pluralize(count: number) {
    return count === 1 ? this.singular : this.plural;
  }

  public get plural(): string {
    return this._plural ?? `${this.singular}s`;
  }
}

export class PluralWords {
  private words: PluralWord[];

  constructor(words: PluralWord[]) {
    this.words = words;
  }

  static of(...words: Array<PluralWord | string>) {
    return new PluralWords(
      words.map((word) => {
        if (typeof word === "string") {
          return new PluralWord(word);
        }
        return word;
      }),
    );
  }

  public join(str: string, count: number) {
    return this.words.map((word) => word.pluralize(count)).join(str);
  }
}
