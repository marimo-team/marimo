/* Copyright 2026 Marimo. All rights reserved. */

import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { Provider, createStore } from "jotai";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MockRequestClient } from "@/__mocks__/requests";
import { ModalProvider } from "@/components/modal/ImperativeModal";
import { TooltipProvider } from "@/components/ui/tooltip";
import { requestClientAtom } from "@/core/network/requests";
import type { FileInfo, FileSearchResponse } from "@/core/network/types";
import { Deferred } from "@/utils/Deferred";
import type { FilePath } from "@/utils/paths";
import { TreeDndProvider } from "../dnd-wrapper";
import { FileExplorer } from "../file-explorer";
import { openStateAtom } from "../state";
import { fileTreeNodeId } from "../requesting-tree";
import { HOVER_EXPAND_DELAY } from "../use-hover-expand";

vi.mock("../file-viewer", () => ({
  FileViewer: ({ file }: { file: FileInfo }) => <div>Preview: {file.name}</div>,
}));

function file(name: string, isDirectory = false): FileInfo {
  return {
    id: name,
    name: name.split("/").at(-1) ?? name,
    path: `/workspace/${name}`,
    isDirectory,
    isMarimoFile: false,
  };
}

function createDragEvents(clientY = 115) {
  const dataTransfer = {
    setData: vi.fn(),
    getData: vi.fn(),
    setDragImage: vi.fn(),
    types: [],
    dropEffect: "move",
    effectAllowed: "all",
  };
  return (target: Element, type: string) => {
    // jsdom has no DragEvent; MouseEvent preserves the pointer coordinates.
    const event = new MouseEvent(type, {
      bubbles: true,
      cancelable: true,
      clientX: 100,
      clientY,
    });
    Object.defineProperty(event, "dataTransfer", { value: dataTransfer });
    fireEvent(target, event);
  };
}

let store = createStore();
let client: ReturnType<typeof MockRequestClient.create>;
const wrapper = ({ children }: { children: ReactNode }) => (
  <Provider store={store}>
    <TooltipProvider>
      <ModalProvider>
        <TreeDndProvider>{children}</TreeDndProvider>
      </ModalProvider>
    </TooltipProvider>
  </Provider>
);

beforeEach(() => {
  localStorage.clear();
  store = createStore();
  client = MockRequestClient.create({
    getFileRoots: vi.fn().mockResolvedValue({
      roots: [{ path: "/workspace", name: "workspace", isPrimary: true }],
    }),
    sendListFiles: vi.fn().mockImplementation(async ({ path }) => ({
      files:
        path === "/workspace"
          ? [file("data", true), file("notes.txt")]
          : [file("data/report.csv")],
    })),
  });
  store.set(requestClientAtom, client);
});

describe("file browser navigation", () => {
  it("debounces the first character, subsequent edits, and searches after clearing", async () => {
    render(<FileExplorer height={300} />, { wrapper });
    const input = await screen.findByRole("textbox", {
      name: "Search files and folders",
    });
    vi.useFakeTimers();
    try {
      fireEvent.change(input, { target: { value: "n" } });
      await act(() => vi.advanceTimersByTimeAsync(100));
      expect(client.sendSearchFiles).not.toHaveBeenCalled();
      fireEvent.change(input, { target: { value: "no" } });
      await act(() => vi.advanceTimersByTimeAsync(299));
      expect(client.sendSearchFiles).not.toHaveBeenCalled();
      await act(() => vi.advanceTimersByTimeAsync(1));
      expect(client.sendSearchFiles).toHaveBeenCalledOnce();
      expect(client.sendSearchFiles).toHaveBeenLastCalledWith(
        expect.objectContaining({ query: "no" }),
      );

      fireEvent.change(input, { target: { value: "" } });
      fireEvent.change(input, { target: { value: "f" } });
      await act(() => vi.advanceTimersByTimeAsync(299));
      expect(client.sendSearchFiles).toHaveBeenCalledOnce();
      await act(() => vi.advanceTimersByTimeAsync(1));
      expect(client.sendSearchFiles).toHaveBeenCalledTimes(2);
      expect(client.sendSearchFiles).toHaveBeenLastCalledWith(
        expect.objectContaining({ query: "f" }),
      );

      fireEvent.change(input, { target: { value: "" } });
      await act(() => vi.advanceTimersByTimeAsync(300));
      expect(client.sendSearchFiles).toHaveBeenCalledTimes(2);
    } finally {
      vi.useRealTimers();
    }
  });

  it("navigates with arrows, opens with Enter, and restores the tree after preview", async () => {
    render(<FileExplorer height={300} />, { wrapper });
    const tree = await screen.findByRole("tree");
    act(() => tree.focus());
    expect(document.activeElement).toHaveTextContent("data");
    fireEvent.keyDown(document.activeElement!, { key: "ArrowRight" });
    expect(client.sendListFiles).toHaveBeenCalledWith({
      path: "/workspace/data",
    });
    expect(await screen.findByText("report.csv")).toBeVisible();
    fireEvent.keyDown(document.activeElement!, { key: "ArrowDown" });
    expect(screen.queryByText("Preview: report.csv")).not.toBeInTheDocument();
    expect(document.activeElement).toHaveTextContent("report.csv");
    fireEvent.keyDown(document.activeElement!, { key: "Enter" });
    expect(await screen.findByText("Preview: report.csv")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Back to files" }));
    expect(await screen.findByText("report.csv")).toBeVisible();
    expect(screen.getByRole("tree")).toBe(tree);
    await waitFor(() =>
      expect(document.activeElement).toHaveTextContent("report.csv"),
    );
  });

  it("bounds mounted rows for a directory with 10,000 files and supports End navigation", async () => {
    client.sendListFiles.mockResolvedValue({
      root: "/workspace",
      files: Array.from({ length: 10_000 }, (_, index) =>
        file(`file-${index}.txt`),
      ),
    });
    render(<FileExplorer height={300} />, { wrapper });
    const tree = await screen.findByRole("tree");
    expect(screen.getAllByRole("treeitem").length).toBeLessThan(40);
    act(() => tree.focus());
    fireEvent.keyDown(document.activeElement!, { key: "End" });
    expect(await screen.findByText("file-9999.txt")).toBeVisible();
    expect(screen.getAllByRole("treeitem").length).toBeLessThan(40);
  });

  it("renames with F2 and keeps leaf files distinct from expandable folders", async () => {
    render(<FileExplorer height={300} />, { wrapper });
    const row = await screen.findByRole("treeitem", { name: "notes.txt" });
    expect(row).not.toHaveAttribute("aria-expanded");
    expect(screen.getByRole("treeitem", { name: "data" })).toHaveAttribute(
      "aria-expanded",
      "false",
    );
    fireEvent.click(screen.getByText("notes.txt"));
    fireEvent.keyDown(row, { key: "F2" });
    expect(await screen.findByDisplayValue("notes.txt")).toHaveFocus();
    fireEvent.keyDown(document.activeElement!, { key: "Escape" });
    expect(client.sendRenameFileOrFolder).not.toHaveBeenCalled();
  });

  it("reveals and expands folders found by search", async () => {
    client.sendSearchFiles.mockResolvedValue({
      files: [file("data", true)],
      query: "data",
      totalFound: 1,
    });
    render(<FileExplorer height={300} />, { wrapper });
    const input = await screen.findByRole("textbox", {
      name: "Search files and folders",
    });
    fireEvent.change(input, { target: { value: "data" } });
    await screen.findByText("1 match");
    fireEvent.keyDown(input, { key: "Enter" });
    expect(await screen.findByText("report.csv")).toBeVisible();
    expect(input).toHaveValue("");
    expect(screen.getByRole("treeitem", { name: "data" })).toHaveAttribute(
      "aria-expanded",
      "true",
    );
  });

  it("finds unopened descendants and supports keyboard activation from the search field", async () => {
    client.sendSearchFiles.mockResolvedValue({
      files: [file("data/report.csv")],
      query: "report",
      totalFound: 1,
    });
    render(<FileExplorer height={300} />, { wrapper });
    const input = await screen.findByRole("textbox", {
      name: "Search files and folders",
    });
    fireEvent.change(input, { target: { value: "report" } });
    expect(await screen.findByText("report.csv")).toBeVisible();
    expect(client.sendSearchFiles).toHaveBeenCalledWith(
      expect.objectContaining({ query: "report", path: "/workspace" }),
    );
    fireEvent.keyDown(input, { key: "ArrowDown" });
    await waitFor(() =>
      expect(document.activeElement).toHaveTextContent("report.csv"),
    );
    fireEvent.keyDown(document.activeElement!, { key: "Enter" });
    expect(await screen.findByText("Preview: report.csv")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Back to files" }));
    expect(input).toHaveValue("report");
    fireEvent.keyDown(input, { key: "Escape" });
    expect(input).toHaveValue("");
  });

  it("previews search files without loading their ancestors", async () => {
    client.sendSearchFiles.mockResolvedValue({
      files: [file("new/nested/report.csv")],
      query: "report",
      totalFound: 1,
    });
    render(<FileExplorer height={300} />, { wrapper });
    const input = await screen.findByRole("textbox", {
      name: "Search files and folders",
    });
    client.sendListFiles.mockClear();
    fireEvent.change(input, { target: { value: "report" } });
    await screen.findByText("1 match");
    fireEvent.keyDown(input, { key: "Enter" });
    expect(await screen.findByText("Preview: report.csv")).toBeVisible();
    expect(client.sendListFiles).not.toHaveBeenCalled();
  });

  it.each([
    { offset: 1, sourceName: "notes.txt", canMove: true },
    { offset: 15, sourceName: "notes.txt", canMove: true },
    { offset: 29, sourceName: "notes.txt", canMove: true },
    { offset: 15, sourceName: "data", canMove: false },
  ])(
    "drops $sourceName at folder offset $offset with canMove=$canMove",
    async ({ offset, sourceName, canMove }) => {
      render(<FileExplorer height={300} />, { wrapper });
      const folder = await screen.findByRole("treeitem", { name: "data" });
      const source = screen.getByRole("treeitem", {
        name: sourceName,
      }).firstElementChild;
      if (!source) {
        throw new Error("Missing drag source");
      }
      vi.spyOn(folder, "getBoundingClientRect").mockReturnValue(
        new DOMRect(0, 100, 300, 30),
      );
      const dragEvent = createDragEvents(100 + offset);
      dragEvent(source, "dragstart");
      await act(async () => {
        await new Promise((resolve) => setTimeout(resolve, 0));
      });
      dragEvent(folder, "dragenter");
      dragEvent(folder, "dragover");
      await act(async () => {
        await new Promise(requestAnimationFrame);
      });
      dragEvent(folder, "drop");
      if (canMove) {
        await waitFor(() =>
          expect(client.sendRenameFileOrFolder).toHaveBeenCalledExactlyOnceWith(
            {
              path: "/workspace/notes.txt",
              newPath: "/workspace/data/notes.txt",
            },
          ),
        );
      } else {
        expect(client.sendRenameFileOrFolder).not.toHaveBeenCalled();
      }
      dragEvent(source, "dragend");
    },
  );

  it("expands hovered folders after a delay and supports nested drops", async () => {
    client.sendListFiles.mockImplementation(async ({ path }) => {
      if (path === "/workspace") {
        return {
          root: "/workspace",
          files: [file("data", true), file("notes.txt")],
        };
      }
      if (path === "/workspace/data") {
        return { root: "/workspace", files: [file("data/nested", true)] };
      }
      return { root: "/workspace", files: [] };
    });
    render(<FileExplorer height={300} />, { wrapper });
    const folder = await screen.findByRole("treeitem", { name: "data" });
    const source = screen.getByRole("treeitem", {
      name: "notes.txt",
    }).firstElementChild;
    if (!source) {
      throw new Error("Missing drag source");
    }
    const dragEvent = createDragEvents();
    vi.useFakeTimers();
    try {
      dragEvent(source, "dragstart");
      await act(async () => {
        await vi.advanceTimersByTimeAsync(0);
      });
      dragEvent(folder, "dragenter");
      dragEvent(folder, "dragover");
      await act(async () => {
        await vi.advanceTimersByTimeAsync(HOVER_EXPAND_DELAY - 1);
      });
      expect(folder).toHaveAttribute("aria-expanded", "false");
      await act(async () => {
        await vi.advanceTimersByTimeAsync(1);
      });
      expect(folder).toHaveAttribute("aria-expanded", "true");
      expect(client.sendListFiles).toHaveBeenCalledWith({
        path: "/workspace/data",
      });
      const nested = screen.getByRole("treeitem", { name: "nested" });
      dragEvent(nested, "dragenter");
      dragEvent(nested, "dragover");
      await act(async () => {
        await vi.advanceTimersByTimeAsync(16);
      });
      await act(async () => {
        await vi.advanceTimersByTimeAsync(HOVER_EXPAND_DELAY);
      });
      expect(nested).toHaveAttribute("aria-expanded", "true");
      expect(client.sendListFiles).toHaveBeenCalledWith({
        path: "/workspace/data/nested",
      });
      await act(async () => {
        dragEvent(nested, "drop");
      });
      expect(client.sendRenameFileOrFolder).toHaveBeenCalledExactlyOnceWith({
        path: "/workspace/notes.txt",
        newPath: "/workspace/data/nested/notes.txt",
      });
      dragEvent(source, "dragend");
    } finally {
      vi.useRealTimers();
    }
  });

  it.each(["leave", "end", "invalid"])(
    "does not expand a folder when the drag is %s",
    async (reason) => {
      render(<FileExplorer height={300} />, { wrapper });
      const folder = await screen.findByRole("treeitem", { name: "data" });
      const sourceRow =
        reason === "invalid"
          ? folder
          : screen.getByRole("treeitem", { name: "notes.txt" });
      const source = sourceRow.firstElementChild;
      if (!source) {
        throw new Error("Missing drag source");
      }
      const dragEvent = createDragEvents();
      vi.useFakeTimers();
      try {
        dragEvent(source, "dragstart");
        await act(async () => {
          await vi.advanceTimersByTimeAsync(0);
        });
        dragEvent(folder, "dragenter");
        dragEvent(folder, "dragover");
        await act(async () => {
          await vi.advanceTimersByTimeAsync(400);
        });
        if (reason === "leave") {
          dragEvent(sourceRow, "dragenter");
          dragEvent(sourceRow, "dragover");
        } else if (reason === "end") {
          dragEvent(source, "dragend");
        }
        await act(async () => {
          await vi.advanceTimersByTimeAsync(1000);
        });
        expect(folder).toHaveAttribute("aria-expanded", "false");
        expect(client.sendListFiles).not.toHaveBeenCalledWith({
          path: "/workspace/data",
        });
        dragEvent(source, "dragend");
      } finally {
        vi.useRealTimers();
      }
    },
  );

  it("expands nested external upload destinations and cancels when the drag leaves", async () => {
    client.sendListFiles.mockImplementation(async ({ path }) => {
      if (path === "/workspace") {
        return { root: "/workspace", files: [file("data", true)] };
      }
      if (path === "/workspace/data") {
        return { root: "/workspace", files: [file("data/nested", true)] };
      }
      return { root: "/workspace", files: [] };
    });
    const { rerender } = render(<FileExplorer height={300} />, { wrapper });
    const folder = await screen.findByRole("treeitem", { name: "data" });
    vi.useFakeTimers();
    try {
      rerender(
        <FileExplorer
          height={300}
          externalDropDestinationPath={"/workspace/data" as FilePath}
        />,
      );
      await act(async () => {
        await vi.advanceTimersByTimeAsync(300);
      });
      rerender(
        <FileExplorer height={300} externalDropDestinationPath={null} />,
      );
      await act(async () => {
        await vi.advanceTimersByTimeAsync(HOVER_EXPAND_DELAY);
      });
      expect(folder).toHaveAttribute("aria-expanded", "false");
      rerender(
        <FileExplorer
          height={300}
          externalDropDestinationPath={"/workspace/data" as FilePath}
        />,
      );
      await act(async () => {
        await vi.advanceTimersByTimeAsync(HOVER_EXPAND_DELAY - 1);
      });
      expect(folder).toHaveAttribute("aria-expanded", "false");
      await act(async () => {
        await vi.advanceTimersByTimeAsync(1);
      });
      expect(folder).toHaveAttribute("aria-expanded", "true");
      const nested = screen.getByRole("treeitem", { name: "nested" });
      rerender(
        <FileExplorer
          height={300}
          externalDropDestinationPath={"/workspace/data/nested" as FilePath}
        />,
      );
      await act(async () => {
        await vi.advanceTimersByTimeAsync(HOVER_EXPAND_DELAY);
      });
      expect(nested).toHaveAttribute("aria-expanded", "true");
      expect(client.sendListFiles).toHaveBeenCalledWith({
        path: "/workspace/data/nested",
      });
      expect(client.sendRenameFileOrFolder).not.toHaveBeenCalled();
    } finally {
      vi.useRealTimers();
    }
  });

  it("ranks matches across roots before applying the global result limit", async () => {
    client.getFileRoots.mockResolvedValue({
      roots: [
        { path: "/workspace", name: "workspace", isPrimary: true },
        { path: "/shared", name: "shared", isPrimary: false },
      ],
    });
    client.sendSearchFiles.mockImplementation(async ({ path, query }) => {
      const files =
        path === "/workspace"
          ? Array.from({ length: 200 }, (_, index) =>
              file(`report-${index}.txt`),
            )
          : [{ ...file("report"), path: "/shared/report" }];
      return { files, query, totalFound: files.length };
    });
    render(<FileExplorer height={300} />, { wrapper });
    const input = await screen.findByRole("textbox", {
      name: "Search files and folders",
    });
    fireEvent.change(input, { target: { value: "report" } });
    await screen.findByText(/200 matches/);
    const results = screen.getAllByRole("treeitem");
    expect(results[0]).toHaveAccessibleName("report");
    expect(
      client.sendSearchFiles.mock.calls.map(([request]) => request.path),
    ).toEqual(["/workspace", "/shared"]);
  });

  it("shows an error when every search root fails", async () => {
    client.sendSearchFiles.mockRejectedValue(new Error("Unavailable"));
    render(<FileExplorer height={300} />, { wrapper });
    const input = await screen.findByRole("textbox", {
      name: "Search files and folders",
    });
    fireEvent.change(input, { target: { value: "report" } });
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Could not search files",
    );
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
  });

  it("retries failed hover expansion only after leaving and reentering", async () => {
    const { rerender } = render(<FileExplorer height={300} />, { wrapper });
    const folder = await screen.findByRole("treeitem", { name: "data" });
    client.sendListFiles.mockRejectedValue(new Error("Unavailable"));
    client.sendListFiles.mockClear();
    vi.useFakeTimers();
    try {
      rerender(
        <FileExplorer
          height={300}
          externalDropDestinationPath={"/workspace/data" as FilePath}
        />,
      );
      await act(async () => {
        await vi.advanceTimersByTimeAsync(HOVER_EXPAND_DELAY);
      });
      expect(folder).toHaveAttribute("aria-expanded", "false");
      await act(async () => {
        await vi.advanceTimersByTimeAsync(HOVER_EXPAND_DELAY * 5);
      });
      expect(client.sendListFiles).toHaveBeenCalledTimes(1);
      rerender(
        <FileExplorer height={300} externalDropDestinationPath={null} />,
      );
      client.sendListFiles.mockResolvedValue({
        root: "/workspace",
        files: [file("data/report.csv")],
      });
      rerender(
        <FileExplorer
          height={300}
          externalDropDestinationPath={"/workspace/data" as FilePath}
        />,
      );
      await act(async () => {
        await vi.advanceTimersByTimeAsync(HOVER_EXPAND_DELAY);
      });
      expect(client.sendListFiles).toHaveBeenCalledTimes(2);
      expect(folder).toHaveAttribute("aria-expanded", "true");
    } finally {
      vi.useRealTimers();
    }
  });

  it("keeps partial results when a root fails, and retries all roots", async () => {
    client.getFileRoots.mockResolvedValue({
      roots: [
        { path: "/workspace", name: "workspace", isPrimary: true },
        { path: "/shared", name: "shared", isPrimary: false },
      ],
    });
    let sharedUnavailable = true;
    client.sendSearchFiles.mockImplementation(async ({ path, query }) => {
      if (path === "/shared" && sharedUnavailable) {
        throw new Error("Storage unavailable");
      }
      return {
        files: [{ ...file("report.txt"), path: `${path}/report.txt` }],
        query,
        totalFound: 1,
      };
    });
    render(<FileExplorer height={300} />, { wrapper });
    const input = await screen.findByRole("textbox", {
      name: "Search files and folders",
    });
    fireEvent.change(input, { target: { value: "report" } });
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Some locations could not be searched",
    );
    expect(
      screen.getByRole("treeitem", { name: "report.txt" }),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("treeitem", { name: "report.txt" }));
    const retry = screen.getByRole("button", { name: "Retry" });
    retry.focus();
    sharedUnavailable = false;
    expect(fireEvent.keyDown(retry, { key: "Enter" })).toBe(true);
    // jsdom does not synthesize a button click from Enter.
    fireEvent.click(retry);
    await screen.findByText("2 matches");
    expect(screen.queryByText("Preview: report.txt")).not.toBeInTheDocument();
    expect(
      client.sendSearchFiles.mock.calls.map(([request]) => request.path),
    ).toEqual(["/workspace", "/shared", "/workspace", "/shared"]);
  });

  it.each([
    { counts: [100, 100], truncated: false },
    { counts: [200, 0], truncated: true },
    { counts: [150, 100], truncated: true },
  ])(
    "reports search truncation correctly for $counts",
    async ({ counts, truncated }) => {
      client.getFileRoots.mockResolvedValue({
        roots: [
          { path: "/workspace", name: "workspace", isPrimary: true },
          { path: "/shared", name: "shared", isPrimary: false },
        ],
      });
      client.sendSearchFiles.mockImplementation(async ({ path, query }) => {
        const count = counts[path === "/workspace" ? 0 : 1];
        const files = Array.from({ length: count }, (_, index) => ({
          ...file(`report-${index}`),
          path: `${path}/report-${index}`,
        }));
        return { files, query, totalFound: files.length };
      });
      render(<FileExplorer height={300} />, { wrapper });
      const input = await screen.findByRole("textbox", {
        name: "Search files and folders",
      });
      fireEvent.change(input, { target: { value: "report" } });
      const status = await screen.findByText(/200 matches/);
      expect(status.textContent?.includes("Refine your search")).toBe(
        truncated,
      );
    },
  );

  it("keeps keyboard navigation aligned with a clicked row", async () => {
    client.sendListFiles.mockResolvedValue({
      root: "/workspace",
      files: [file("a.txt"), file("b.txt"), file("c.txt")],
    });
    render(<FileExplorer height={300} />, { wrapper });
    const middle = await screen.findByRole("treeitem", { name: "b.txt" });
    fireEvent.click(screen.getByText("b.txt"));
    expect(middle).toHaveFocus();
    fireEvent.keyDown(middle, { key: "ArrowDown" });
    expect(screen.getByRole("treeitem", { name: "c.txt" })).toHaveFocus();
  });

  it("closes failed expansions without persisting them and allows retry", async () => {
    render(<FileExplorer height={300} />, { wrapper });
    const folder = await screen.findByRole("treeitem", { name: "data" });
    client.sendListFiles.mockRejectedValueOnce(new Error("Offline"));
    fireEvent.click(folder);
    fireEvent.keyDown(folder, { key: "ArrowRight" });
    await waitFor(() =>
      expect(folder).toHaveAttribute("aria-expanded", "false"),
    );
    expect(
      store.get(openStateAtom)[fileTreeNodeId("/workspace", "/workspace/data")],
    ).toBe(false);
    fireEvent.keyDown(folder, { key: "ArrowRight" });
    expect(
      await screen.findByRole("treeitem", { name: "report.csv" }),
    ).toBeVisible();
  });

  it("focuses a clicked search result so Enter opens that result", async () => {
    client.sendSearchFiles.mockResolvedValue({
      files: [file("report-first.txt"), file("report-second.txt")],
      query: "report",
      totalFound: 2,
    });
    render(<FileExplorer height={300} />, { wrapper });
    const input = await screen.findByRole("textbox", {
      name: "Search files and folders",
    });
    input.focus();
    fireEvent.change(input, { target: { value: "report" } });
    await screen.findByText("2 matches");
    fireEvent.click(screen.getByText("report-second.txt"));
    const second = screen.getByRole("treeitem", { name: "report-second.txt" });
    expect(second).toHaveFocus();
    fireEvent.keyDown(second, { key: "Enter" });
    expect(await screen.findByText("Preview: report-second.txt")).toBeVisible();
  });

  it("passes hidden-file visibility to search and refetches when it changes", async () => {
    client.sendSearchFiles.mockResolvedValue({
      files: [],
      query: "note",
      totalFound: 0,
    });
    render(<FileExplorer height={300} />, { wrapper });
    const input = await screen.findByRole("textbox", {
      name: "Search files and folders",
    });
    fireEvent.change(input, { target: { value: "note" } });
    await screen.findByText("No matching files or folders.");
    expect(client.sendSearchFiles).toHaveBeenLastCalledWith(
      expect.objectContaining({ includeHidden: true }),
    );
    fireEvent.click(screen.getByTestId("file-explorer-hidden-files-button"));
    await waitFor(() =>
      expect(client.sendSearchFiles).toHaveBeenLastCalledWith(
        expect.objectContaining({ includeHidden: false }),
      ),
    );
  });

  it("coalesces superseded searches without overlapping server scans", async () => {
    const slow = new Deferred<FileSearchResponse>();
    client.sendSearchFiles
      .mockReturnValueOnce(slow.promise)
      .mockResolvedValueOnce({
        files: [file("notes.txt")],
        query: "notes",
        totalFound: 1,
      });
    render(<FileExplorer height={300} />, { wrapper });
    const input = await screen.findByRole("textbox", {
      name: "Search files and folders",
    });
    fireEvent.change(input, { target: { value: "report" } });
    await waitFor(() => expect(client.sendSearchFiles).toHaveBeenCalledOnce());
    fireEvent.change(input, { target: { value: "notes" } });
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 350));
    });
    expect(client.sendSearchFiles).toHaveBeenCalledOnce();
    fireEvent.change(input, { target: { value: "note" } });
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 350));
    });
    expect(client.sendSearchFiles).toHaveBeenCalledOnce();
    await act(async () => {
      slow.resolve({
        files: [file("data/report.csv")],
        query: "report",
        totalFound: 1,
      });
    });
    await screen.findByText("1 match");
    expect(client.sendSearchFiles).toHaveBeenCalledTimes(2);
    expect(client.sendSearchFiles).toHaveBeenLastCalledWith(
      expect.objectContaining({ query: "note" }),
    );
    expect(screen.getByRole("treeitem", { name: "notes.txt" })).toBeVisible();
    expect(
      screen.queryByRole("treeitem", { name: "report.csv" }),
    ).not.toBeInTheDocument();
  });
});
