/* Copyright 2024 Marimo. All rights reserved. */
import { describe, test, expect } from "vitest";
import { PluralWord, PluralWords } from "../pluralize";

describe("PluralWord", () => {
  test("should use default plural form (adding 's')", () => {
    const word = new PluralWord("cat");
    expect(word.plural).toBe("cats");
    expect(word.pluralize(1)).toBe("cat");
    expect(word.pluralize(2)).toBe("cats");
  });

  test("should use custom plural form", () => {
    const word = new PluralWord("child", "children");
    expect(word.plural).toBe("children");
    expect(word.pluralize(1)).toBe("child");
    expect(word.pluralize(2)).toBe("children");
  });

  test("should handle zero as plural", () => {
    const word = new PluralWord("dog");
    expect(word.pluralize(0)).toBe("dogs");
  });
});

describe("PluralWords", () => {
  test("should create from strings", () => {
    const words = PluralWords.of("cat", "dog");
    expect(words.join(" and ", 1)).toBe("cat and dog");
    expect(words.join(" and ", 2)).toBe("cats and dogs");
  });

  test("should create from PluralWord instances", () => {
    const words = PluralWords.of(
      new PluralWord("child", "children"),
      new PluralWord("mouse", "mice"),
    );
    expect(words.join(", ", 1)).toBe("child, mouse");
    expect(words.join(", ", 2)).toBe("children, mice");
  });

  test("should mix strings and PluralWord instances", () => {
    const words = PluralWords.of("cat", new PluralWord("person", "people"));
    expect(words.join(" and ", 1)).toBe("cat and person");
    expect(words.join(" and ", 2)).toBe("cats and people");
  });
});
