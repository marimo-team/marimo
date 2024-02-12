/* Copyright 2024 Marimo. All rights reserved. */
import { describe, expect, it } from "vitest";
import { Paths } from "../paths";

describe("Paths", () => {
  describe("dirname", () => {
    it("should return the directory path of a given path", () => {
      expect(Paths.dirname("/user/docs/Letter.txt")).toBe("/user/docs");
    });

    it("should return an empty string if the path is a root directory", () => {
      expect(Paths.dirname("/")).toBe("");
      expect(Paths.dirname("")).toBe("");
    });

    it("should handle paths without a leading slash", () => {
      expect(Paths.dirname("user/docs/Letter.txt")).toBe("user/docs");
    });

    it("should handle windows-style paths", () => {
      expect(Paths.dirname("C:\\user\\docs\\Letter.txt")).toBe(
        "C:\\user\\docs",
      );
    });
  });

  describe("basename", () => {
    it("should return the last part of a path", () => {
      expect(Paths.basename("/user/docs/Letter.txt")).toBe("Letter.txt");
    });

    it("should return an empty string if the path ends with a slash", () => {
      expect(Paths.basename("/user/docs/")).toBe("");
    });

    it("should handle paths without a leading slash", () => {
      expect(Paths.basename("user/docs/Letter.txt")).toBe("Letter.txt");
    });

    it("should handle windows-style paths", () => {
      expect(Paths.basename("C:\\user\\docs\\Letter.txt")).toBe("Letter.txt");
    });
  });
});
