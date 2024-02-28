/* Copyright 2024 Marimo. All rights reserved. */
import { describe, expect, it } from "vitest";
import { FilePath, PathBuilder, Paths } from "../paths";

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

describe("PathBuilder", () => {
  describe("constructor and guessDeliminator", () => {
    it('should create instance with "/" delimiter', () => {
      const pathBuilder = new PathBuilder("/");
      expect(pathBuilder.join("path", "to", "file")).toBe("path/to/file");
    });

    it('should create instance with "\\" delimiter', () => {
      const pathBuilder = new PathBuilder("\\");
      expect(pathBuilder.join("path", "to", "file")).toBe("path\\to\\file");
    });

    it('guessDeliminator should choose "/" for paths with "/"', () => {
      const pathBuilder = PathBuilder.guessDeliminator("path/to/file");
      expect(pathBuilder.join("path", "to", "file")).toBe("path/to/file");
    });

    it('guessDeliminator should choose "\\" for paths with "\\"', () => {
      const pathBuilder = PathBuilder.guessDeliminator("path\\to\\file");
      expect(pathBuilder.join("path", "to", "file")).toBe("path\\to\\file");
    });
  });

  describe("join", () => {
    it('should join paths with "/"', () => {
      const pathBuilder = new PathBuilder("/");
      expect(pathBuilder.join("path", "to", "file")).toBe("path/to/file");
    });

    it('should join paths with "\\"', () => {
      const pathBuilder = new PathBuilder("\\");
      expect(pathBuilder.join("path", "to", "file")).toBe("path\\to\\file");
    });

    it("should ignore empty strings and null values", () => {
      const pathBuilder = new PathBuilder("/");
      expect(pathBuilder.join("", "path", null!, "to", "", "file")).toBe(
        "path/to/file",
      );
    });
  });

  describe("basename", () => {
    it('should get basename with "/"', () => {
      const pathBuilder = new PathBuilder("/");
      expect(pathBuilder.basename("path/to/file" as FilePath)).toBe("file");
    });

    it('should get basename with "\\"', () => {
      const pathBuilder = new PathBuilder("\\");
      expect(pathBuilder.basename("path\\to\\file" as FilePath)).toBe("file");
    });

    it("should return empty string if no basename", () => {
      const pathBuilder = new PathBuilder("/");
      expect(pathBuilder.basename("/" as FilePath)).toBe("");
    });
  });

  describe("dirname", () => {
    it('should get dirname with "/"', () => {
      const pathBuilder = new PathBuilder("/");
      expect(pathBuilder.dirname("path/to/file" as FilePath)).toBe("path/to");
    });

    it('should get dirname with "\\"', () => {
      const pathBuilder = new PathBuilder("\\");
      expect(pathBuilder.dirname("path\\to\\file" as FilePath)).toBe(
        "path\\to",
      );
    });

    it("should return empty string if no dirname (root directory)", () => {
      const pathBuilder = new PathBuilder("/");
      expect(pathBuilder.dirname("file" as FilePath)).toBe("");
    });
  });
});
