/* Copyright 2024 Marimo. All rights reserved. */
import { describe, expect, it } from "vitest";
import { EDGE_CASE_FILENAMES } from "../../__tests__/mocks";
import { type FilePath, PathBuilder, Paths } from "../paths";

describe("Paths", () => {
  it("isAbsolute", () => {
    expect(Paths.isAbsolute("/")).toBe(true);
    expect(Paths.isAbsolute("/user/docs/Letter.txt")).toBe(true);
    expect(Paths.isAbsolute("C:\\user\\docs\\Letter.txt")).toBe(true);
    expect(Paths.isAbsolute("user/docs/Letter.txt")).toBe(false);
  });

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

  describe("rest", () => {
    it("should return the suffix of a path", () => {
      expect(Paths.rest("/user/docs/Letter.txt", "/user/docs")).toBe(
        "Letter.txt",
      );
      expect(Paths.rest("/user/docs/Letter.txt", "/user/docs/")).toBe(
        "Letter.txt",
      );
      expect(Paths.rest("/user/docs/Letter.txt", "/user")).toBe(
        "docs/Letter.txt",
      );
      expect(Paths.rest("/user/docs/Letter.txt", "/user/")).toBe(
        "docs/Letter.txt",
      );
    });

    it("should handle windows-style paths", () => {
      expect(Paths.rest("C:\\user\\docs\\Letter.txt", "C:\\user\\docs")).toBe(
        "Letter.txt",
      );
      expect(Paths.rest("C:\\user\\docs\\Letter.txt", "C:\\user\\docs\\")).toBe(
        "Letter.txt",
      );
      expect(Paths.rest("C:\\user\\docs\\Letter.txt", "C:\\user")).toBe(
        "docs\\Letter.txt",
      );
      expect(Paths.rest("C:\\user\\docs\\Letter.txt", "C:\\user\\")).toBe(
        "docs\\Letter.txt",
      );
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

  describe("extension", () => {
    it("should return the extension of a file", () => {
      expect(Paths.extension("file.txt")).toBe("txt");
      expect(Paths.extension("file")).toBe("");
      expect(Paths.extension("file.tar.gz")).toBe("gz");
    });
  });

  describe("edge case filenames", () => {
    it.each(
      EDGE_CASE_FILENAMES,
    )("should handle unicode and spaces in basename: %s", (filename) => {
      const basename = Paths.basename(filename);
      expect(basename).toBe(filename);
      expect(typeof basename).toBe("string");
      expect(basename).not.toBe("");
    });

    it.each(
      EDGE_CASE_FILENAMES,
    )("should handle unicode and spaces in dirname: %s", (filename) => {
      const fullPath = `/path/to/${filename}`;
      const dirname = Paths.dirname(fullPath);
      expect(dirname).toBe("/path/to");
    });

    it.each(
      EDGE_CASE_FILENAMES,
    )("should handle unicode and spaces in path operations: %s", (filename) => {
      const baseName = Paths.basename(filename);
      const extension = Paths.extension(filename);

      // Should preserve unicode characters in basename
      expect(baseName).toContain(filename.split(".")[0]);

      // Should correctly extract extension
      if (filename.includes(".")) {
        expect(extension).toBe(filename.split(".").pop());
      }
    });
  });
});
