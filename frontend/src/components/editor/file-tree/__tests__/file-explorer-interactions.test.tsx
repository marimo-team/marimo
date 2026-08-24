/* Copyright 2026 Marimo. All rights reserved. */

import { fireEvent, render, screen } from "@testing-library/react";
import { Provider } from "jotai";
import type React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MockRequestClient } from "@/__mocks__/requests";
import { TooltipProvider } from "@/components/ui/tooltip";
import { requestClientAtom } from "@/core/network/requests";
import type { FileInfo } from "@/core/network/types";
import { store } from "@/core/state/jotai";
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

const wrapper = ({ children }: { children: React.ReactNode }) => (
  <Provider store={store}>
    <TooltipProvider>{children}</TooltipProvider>
  </Provider>
);

describe("FileExplorer upload destination", () => {
  beforeEach(() => {
    store.set(
      requestClientAtom,
      MockRequestClient.create({
        sendListFiles: vi.fn().mockResolvedValue({
          root: "/workspace",
          files: [
            {
              id: "data-directory",
              name: "data",
              path: "/workspace/data",
              isDirectory: true,
            },
          ],
        }),
      }),
    );
  });

  it("uses the selected folder for toolbar uploads", async () => {
    render(<FileExplorer height={300} />, { wrapper });

    const rootUpload = await screen.findByRole("button", {
      name: "Upload files to workspace root",
    });
    expect(rootUpload).toBeVisible();

    fireEvent.click(await screen.findByText("data"));

    expect(
      await screen.findByRole("button", { name: "Upload files to data" }),
    ).toBeVisible();
  });
});
