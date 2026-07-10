/* Copyright 2026 Marimo. All rights reserved. */

import { beforeEach, describe, expect, it, vi } from "vitest";
import { HTTPError } from "@/utils/errors";

const toastMock = vi.fn();
vi.mock("@/components/ui/use-toast", () => ({
  toast: (...args: unknown[]) => toastMock(...args),
}));

import { createErrorToastingRequests } from "../requests-toasting";
import type { EditRequests, RunRequests } from "../types";

function requestsThatReject(error: unknown): EditRequests & RunRequests {
  return createErrorToastingRequests({
    sendRun: vi.fn().mockRejectedValue(error),
  } as unknown as EditRequests & RunRequests);
}

describe("createErrorToastingRequests", () => {
  beforeEach(() => {
    toastMock.mockClear();
  });

  it("suppresses the error toast for a capability 403", async () => {
    const requests = requestsThatReject(
      new HTTPError(403, "Forbidden", {
        detail: "This connection is read-only for this action.",
      }),
    );
    await expect(requests.sendRun({} as never)).rejects.toBeInstanceOf(
      HTTPError,
    );
    expect(toastMock).not.toHaveBeenCalled();
  });

  it("shows a danger toast for other request errors", async () => {
    const requests = requestsThatReject(new HTTPError(500, "Server Error"));
    await expect(requests.sendRun({} as never)).rejects.toBeInstanceOf(
      HTTPError,
    );
    expect(toastMock).toHaveBeenCalledWith(
      expect.objectContaining({ variant: "danger" }),
    );
  });
});
