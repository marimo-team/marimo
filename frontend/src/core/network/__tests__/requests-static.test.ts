/* Copyright 2026 Marimo. All rights reserved. */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { toast } from "@/components/ui/use-toast";
import { createStaticRequests } from "../requests-static";

vi.mock("@/components/ui/use-toast", () => ({ toast: vi.fn() }));

describe("createStaticRequests static-notebook toast", () => {
  beforeEach(() => {
    vi.mocked(toast).mockClear();
  });

  it("requests a once-toast with a stable id on component value updates", async () => {
    const requests = createStaticRequests();
    await requests.sendComponentValues({} as never);

    expect(toast).toHaveBeenCalledWith(
      expect.objectContaining({ id: "static-notebook", once: true }),
    );
  });

  it("uses the same once-toast for function requests", async () => {
    const requests = createStaticRequests();
    await requests.sendFunctionRequest({} as never);

    expect(toast).toHaveBeenCalledWith(
      expect.objectContaining({ id: "static-notebook", once: true }),
    );
  });
});
