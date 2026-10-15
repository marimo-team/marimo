/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import { cn } from "../cn";

describe("cn", () => {
  it("keeps custom font-size tokens next to text colors", () => {
    expect(cn("text-xs-plus text-muted-foreground")).toBe(
      "text-xs-plus text-muted-foreground",
    );
    expect(cn("text-sm-minus text-destructive")).toBe(
      "text-sm-minus text-destructive",
    );
    expect(cn("text-10 text-primary")).toBe("text-10 text-primary");
  });

  it("still resolves conflicts between font sizes", () => {
    expect(cn("text-sm text-xs-plus")).toBe("text-xs-plus");
    expect(cn("text-13 text-xs")).toBe("text-xs");
  });

  it("still resolves conflicts between text colors", () => {
    expect(cn("text-muted-foreground text-primary")).toBe("text-primary");
  });
});
