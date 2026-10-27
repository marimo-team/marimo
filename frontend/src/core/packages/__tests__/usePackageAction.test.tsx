/* Copyright 2026 Marimo. All rights reserved. */
import { act, renderHook } from "@testing-library/react";
import { createStore, Provider } from "jotai";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MockRequestClient } from "@/__mocks__/requests";
import { toast } from "@/components/ui/use-toast";
import { requestClientAtom } from "@/core/network/requests";
import type { PackageOperationResponse } from "@/core/network/types";
import { usePackageAction } from "../usePackageAction";

vi.mock("@/components/ui/use-toast", () => ({ toast: vi.fn() }));

function setup(action: "upgrade" | "remove") {
  const client = MockRequestClient.create();
  const store = createStore();
  store.set(requestClientAtom, client);
  return {
    request: vi.mocked(
      action === "upgrade" ? client.addPackage : client.removePackage,
    ),
    ...renderHook(
      () =>
        usePackageAction(action, "numpy", [{ kind: "group", value: "dev" }]),
      {
        wrapper: ({ children }) => (
          <Provider store={store}>{children}</Provider>
        ),
      },
    ),
  };
}

describe("usePackageAction", () => {
  beforeEach(() => vi.clearAllMocks());

  it.each([
    { action: "upgrade", title: "Package upgraded", upgrade: true },
    { action: "remove", title: "Package removed" },
  ] as const)(
    "preserves dependency groups and prevents duplicate $action requests",
    async ({ action, title, ...options }) => {
      const { result, request } = setup(action);
      const { promise, resolve } =
        Promise.withResolvers<PackageOperationResponse>();
      request.mockReturnValue(promise);
      let pending: Promise<void>;
      act(() => {
        pending = result.current.run();
      });
      expect(result.current.loading).toBe(true);
      await act(async () => {
        await result.current.run();
      });
      expect(request).toHaveBeenCalledExactlyOnceWith({
        package: "numpy",
        group: "dev",
        ...options,
      });
      await act(async () => {
        resolve({ success: true });
        await pending;
      });
      expect(result.current.loading).toBe(false);
      expect(toast).toHaveBeenCalledExactlyOnceWith(
        expect.objectContaining({ title }),
      );
    },
  );

  it("reports saved changes requiring a restart without claiming success", async () => {
    const { result, request } = setup("upgrade");
    request.mockResolvedValue({ success: false, restartRequired: true });
    await act(async () => {
      await result.current.run();
    });
    expect(toast).toHaveBeenCalledExactlyOnceWith(
      expect.objectContaining({
        title: "Changes saved — restart required",
      }),
    );
  });

  it.each([
    {
      response: { success: false, error: "resolver failed" },
      description: "resolver failed",
    },
    { response: { success: false }, description: expect.any(String) },
  ])(
    "reports failed responses as errors: $response",
    async ({ response, description }) => {
      const { result, request } = setup("remove");
      request.mockResolvedValue(response);
      await act(async () => {
        await result.current.run();
      });
      expect(toast).toHaveBeenCalledExactlyOnceWith(
        expect.objectContaining({
          title: "Failed to remove package",
          description,
          variant: "danger",
        }),
      );
    },
  );

  it("reports request errors and allows a retry", async () => {
    const { result, request } = setup("remove");
    request.mockRejectedValueOnce(new Error("offline"));
    await act(async () => {
      await result.current.run();
    });
    expect(toast).toHaveBeenCalledExactlyOnceWith(
      expect.objectContaining({
        title: "Failed to remove package",
        description: "offline",
        variant: "danger",
      }),
    );
    expect(result.current.loading).toBe(false);
    request.mockResolvedValue({ success: true });
    await act(async () => {
      await result.current.run();
    });
    expect(toast).toHaveBeenLastCalledWith(
      expect.objectContaining({ title: "Package removed" }),
    );
  });
});
