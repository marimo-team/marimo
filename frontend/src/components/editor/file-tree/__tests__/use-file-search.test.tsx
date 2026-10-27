/* Copyright 2026 Marimo. All rights reserved. */

import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { EditRequests } from "@/core/network/types";
import { Deferred } from "@/utils/Deferred";
import { RequestingTree } from "../requesting-tree";
import { useFileSearch } from "../use-file-search";

const sendSearchFiles = vi.hoisted(() =>
  vi.fn<EditRequests["sendSearchFiles"]>(),
);
vi.mock("@/core/network/requests", () => ({
  useRequestClient: () => ({ sendSearchFiles }),
}));

describe("useFileSearch", () => {
  let tree: RequestingTree;

  beforeEach(async () => {
    sendSearchFiles.mockReset();
    tree = new RequestingTree({
      getRoots: vi.fn().mockResolvedValue({
        roots: [{ path: "/root", name: "workspace", isPrimary: true }],
      }),
      listFiles: vi.fn().mockResolvedValue({ files: [], root: "/root" }),
      createFileOrFolder: vi.fn(),
      deleteFileOrFolder: vi.fn(),
      copyFileOrFolder: vi.fn(),
      renameFileOrFolder: vi.fn(),
    });
    await tree.initialize(() => undefined);
  });

  it("derives loading for a refetch and a changed hidden-file filter", async () => {
    sendSearchFiles.mockResolvedValue({
      files: [],
      query: "file",
      totalFound: 0,
    });
    const { result, rerender } = renderHook(
      ({ showHiddenFiles }) =>
        useFileSearch({ query: "file", tree, showHiddenFiles }),
      { initialProps: { showHiddenFiles: false } },
    );
    await waitFor(() => expect(result.current.state.status).toBe("success"));

    const pending = new Deferred<
      Awaited<ReturnType<EditRequests["sendSearchFiles"]>>
    >();
    sendSearchFiles.mockReturnValue(pending.promise);
    act(() => result.current.refetch());
    expect(result.current.state.status).toBe("loading");
    await act(async () =>
      pending.resolve({ files: [], query: "file", totalFound: 0 }),
    );
    expect(result.current.state.status).toBe("success");

    sendSearchFiles.mockReturnValue(new Promise(() => undefined));
    rerender({ showHiddenFiles: true });
    expect(result.current.state.status).toBe("loading");
    await waitFor(() =>
      expect(sendSearchFiles).toHaveBeenLastCalledWith(
        expect.objectContaining({ includeHidden: true }),
      ),
    );
  });

  it("keeps superseded scans serial and ignores their results", async () => {
    const first = new Deferred<
      Awaited<ReturnType<EditRequests["sendSearchFiles"]>>
    >();
    sendSearchFiles
      .mockReturnValueOnce(first.promise)
      .mockResolvedValue({ files: [], query: "file", totalFound: 0 });
    const { result } = renderHook(() =>
      useFileSearch({ query: "file", tree, showHiddenFiles: false }),
    );
    await waitFor(() => expect(sendSearchFiles).toHaveBeenCalledOnce());

    act(() => result.current.refetch());
    expect(sendSearchFiles).toHaveBeenCalledOnce();
    expect(result.current.state.status).toBe("loading");
    await act(async () =>
      first.resolve({ files: [], query: "file", totalFound: 0 }),
    );

    expect(sendSearchFiles).toHaveBeenCalledTimes(2);
    expect(result.current.state.status).toBe("success");
  });
});
