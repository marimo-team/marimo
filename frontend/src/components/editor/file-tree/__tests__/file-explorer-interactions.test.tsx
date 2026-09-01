/* Copyright 2026 Marimo. All rights reserved. */

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { Provider, createStore } from "jotai";
import type React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MockRequestClient } from "@/__mocks__/requests";
import { TooltipProvider } from "@/components/ui/tooltip";
import { requestClientAtom } from "@/core/network/requests";
import type { FileInfo } from "@/core/network/types";
import { FileExplorer } from "../file-explorer";

vi.mock("react-arborist", async (importOriginal) => {
  const actual = await importOriginal<typeof import("react-arborist")>();
  return {
    ...actual,
    Tree: ({
      data,
      onSelect,
    }: {
      data: FileInfo[];
      onSelect: (nodes: Array<{ data: FileInfo }>) => void;
    }) => (
      <div>
        {data.map((item) => (
          <button
            type="button"
            key={item.id}
            onClick={() => onSelect([{ data: item }])}
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
      sendListFiles: vi.fn().mockImplementation(async ({ path }) => {
        if (path) {
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

    const rootUpload = await screen.findByRole("button", {
      name: "Upload files to workspace root",
    });
    expect(rootUpload).toBeVisible();

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

    fireEvent.click(await screen.findByText(".hidden"));
    expect(
      await screen.findByRole("button", { name: "Upload files to .hidden" }),
    ).toBeVisible();

    fireEvent.click(screen.getByTestId("file-explorer-hidden-files-button"));

    expect(
      await screen.findByRole("button", {
        name: "Upload files to workspace root",
      }),
    ).toBeVisible();
    expect(screen.queryByText(".hidden")).not.toBeInTheDocument();
  });
});
