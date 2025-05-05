/* Copyright 2024 Marimo. All rights reserved. */
import { describe, it, expect } from "vitest";
import { replaceInvalid } from "../write-secret-modal";

describe("replaceInvalid", () => {
  it("should replace spaces with underscores", () => {
    expect(replaceInvalid("secret name")).toBe("secret_name");
  });

  it("should replace hyphens with underscores", () => {
    expect(replaceInvalid("secret-name")).toBe("secret_name");
  });

  it("should replace multiple invalid characters with underscores", () => {
    expect(replaceInvalid("secret name-with-hyphens")).toBe(
      "secret_name_with_hyphens",
    );
  });

  it("should handle leading and trailing invalid characters", () => {
    expect(replaceInvalid("-secret name-")).toBe("_secret_name_");
  });

  it("should handle consecutive invalid characters", () => {
    expect(replaceInvalid("secret--name  with spaces")).toBe(
      "secret__name__with_spaces",
    );
  });

  it("should not replace valid characters (alphanumeric and underscore)", () => {
    expect(replaceInvalid("valid_secret_name_123")).toBe(
      "valid_secret_name_123",
    );
  });

  it("should return an empty string if the input is empty", () => {
    expect(replaceInvalid("")).toBe("");
  });

  it("should handle strings with only invalid characters", () => {
    expect(replaceInvalid(" - ")).toBe("___");
  });
});
