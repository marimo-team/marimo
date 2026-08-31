/* Copyright 2026 Marimo. All rights reserved. */

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { Provider, createStore } from "jotai";
import type React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MockRequestClient } from "@/__mocks__/requests";
import { TooltipProvider } from "@/components/ui/tooltip";
import { requestClientAtom } from "@/core/network/requests";
import { FileExplorer } from "../file-explorer";
import type { FileTreeNode } from "../requesting-tree";

vi.mock("react-arborist", async (importOriginal) => {
  const actual = await importOriginal<typeof import("react-arborist")>();
  return {
    ...actual,
    Tree: ({
      data,
      onSelect,
      onToggle,
    }: {
      data: FileTreeNode[];
      onSelect: (nodes: Array<{ id: string; data: FileTreeNode }>) => void;
      onToggle: (id: string) => void;
    }) => (
      <div>
        {data
          .flatMap((item) => [item, ...item.children])
          .map((item) => (
            <button
              type="button"
              key={item.id}
              onClick={() => {
                onSelect([{ id: item.id, data: item }]);
                if (item.isDirectory) {
                  void onToggle(item.id);
                }
              }}
            >
              {item.name}
            </button>
          ))}
      </div>
    ),
  };
});

let testStore = createStore();

const wrapper = ({ children }: { children: React.ReactNode }) => (
  <Provider store={testStore}>
    <TooltipProvider>{children}</TooltipProvider>
  </Provider>
);

describe("FileExplorer upload destination", () => {
  let client: ReturnType<typeof MockRequestClient.create>;

  beforeEach(() => {
    localStorage.removeItem("marimo:showHiddenFiles");
    testStore = createStore();
    client = MockRequestClient.create({
      getFileRoots: vi.fn().mockResolvedValue({
        roots: [{ path: "/workspace", name: "workspace", isPrimary: true }],
      }),
      sendListFiles: vi.fn().mockImplementation(async ({ path }) => {
        if (path !== "/workspace") {
          return { files: [] };
        }
        return {
          root: "/workspace",
          files: [
            {
              id: "data-directory",
              name: "data",
              path: "/workspace/data",
              isDirectory: true,
            },
            {
              id: "hidden-directory",
              name: ".hidden",
              path: "/workspace/.hidden",
              isDirectory: true,
            },
          ],
        };
      }),
      sendCreateFileOrFolder: vi.fn().mockResolvedValue({ success: true }),
    });
    testStore.set(requestClientAtom, client);
  });

  it("uses the selected folder for toolbar uploads", async () => {
    render(<FileExplorer height={300} />, { wrapper });

    expect(
      await screen.findByRole("button", {
        name: "Upload files to workspace",
      }),
    ).toBeVisible();

    fireEvent.click(await screen.findByText("workspace"));

    expect(
      await screen.findByRole("button", {
        name: "Upload files to workspace",
      }),
    ).toBeVisible();

    fireEvent.click(await screen.findByText("data"));

    const folderUpload = await screen.findByRole("button", {
      name: "Upload files to data",
    });
    fireEvent.click(folderUpload);

    const file = new File(["contents"], "report.csv");
    fireEvent.change(screen.getByTestId("file-explorer-upload-input"), {
      target: { files: [file] },
    });

    await waitFor(() => {
      expect(client.sendCreateFileOrFolder).toHaveBeenCalledWith({
        path: "/workspace/data",
        type: "file",
        name: "report.csv",
        file,
      });
    });
  });

  it("clears a selected hidden folder when hidden files are hidden", async () => {
    render(<FileExplorer height={300} />, { wrapper });

    fireEvent.click(await screen.findByText("workspace"));
    fireEvent.click(await screen.findByText(".hidden"));
    expect(
      await screen.findByRole("button", { name: "Upload files to .hidden" }),
    ).toBeVisible();

    fireEvent.click(screen.getByTestId("file-explorer-hidden-files-button"));

    expect(
      await screen.findByRole("button", {
        name: "Upload files to workspace",
      }),
    ).toBeVisible();
    expect(screen.queryByText(".hidden")).not.toBeInTheDocument();
  });
});
