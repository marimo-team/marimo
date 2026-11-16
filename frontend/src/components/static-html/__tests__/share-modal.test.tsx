/* Copyright 2026 Marimo. All rights reserved. */

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { Dialog } from "@/components/ui/dialog";
import { TooltipProvider } from "@/components/ui/tooltip";
import { ShareStaticNotebookModal } from "../share-modal";
import { stageForPublish } from "../stage-for-publish";

const exportAsHTML = vi.fn();

vi.mock("@/core/network/requests", () => ({
  useRequestClient: () => ({ exportAsHTML }),
}));
vi.mock("@/core/export/layout", () => ({
  getExportLayout: vi.fn().mockResolvedValue(undefined),
}));
vi.mock("@/core/static/virtual-file-tracker", () => ({
  VirtualFileTracker: { INSTANCE: { filenames: () => [] } },
}));
vi.mock("../stage-for-publish", () => ({
  stageForPublish: vi.fn(),
}));

const stageForPublishMock = vi.mocked(stageForPublish);
const CLAIM_URL = "https://claim.example/abc";

function wrapper({ children }: { children: React.ReactNode }) {
  return (
    <TooltipProvider>
      <Dialog open={true}>{children}</Dialog>
    </TooltipProvider>
  );
}

describe("ShareStaticNotebookModal", () => {
  const onClose = vi.fn();
  const windowOpen = vi.fn<typeof window.open>();

  beforeEach(() => {
    vi.clearAllMocks();
    vi.stubGlobal("open", windowOpen);
    exportAsHTML.mockResolvedValue({
      contents: "<html></html>",
      filename: "nb.html",
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  function renderModal() {
    return render(<ShareStaticNotebookModal onClose={onClose} />, {
      wrapper,
    });
  }

  it("exports with CDN assets, opens the claim page, and keeps the link in the dialog", async () => {
    stageForPublishMock.mockResolvedValue(CLAIM_URL);
    renderModal();

    fireEvent.click(screen.getByTestId("share-static-notebook-button"));

    const link = await screen.findByTestId("open-claim-page-link");
    expect(link).toHaveAttribute("href", CLAIM_URL);
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
    expect(link).toHaveAttribute("target", "_blank");

    expect(windowOpen).toHaveBeenCalledWith(
      CLAIM_URL,
      "_blank",
      "noopener,noreferrer",
    );
    expect(exportAsHTML).toHaveBeenCalledWith(
      expect.objectContaining({
        includeCode: true,
        download: false,
        assetUrl: expect.stringContaining("cdn.jsdelivr.net"),
      }),
    );
    expect(stageForPublishMock).toHaveBeenCalledWith(
      "nb.html",
      "<html></html>",
    );
    // The dialog stays open so the link survives a blocked popup.
    expect(onClose).not.toHaveBeenCalled();
    expect(
      screen.queryByTestId("share-static-notebook-button"),
    ).not.toBeInTheDocument();
  });

  it("closes from the staged view via Done", async () => {
    stageForPublishMock.mockResolvedValue(CLAIM_URL);
    renderModal();

    fireEvent.click(screen.getByTestId("share-static-notebook-button"));
    fireEvent.click(
      await screen.findByTestId("done-share-static-notebook-button"),
    );

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("shows the failure in the dialog and allows retrying", async () => {
    stageForPublishMock
      .mockRejectedValueOnce(new Error("Too many uploads, try again later"))
      .mockResolvedValueOnce(CLAIM_URL);
    renderModal();

    fireEvent.click(screen.getByTestId("share-static-notebook-button"));

    const error = await screen.findByTestId("share-static-notebook-error");
    expect(error).toHaveTextContent(
      "Publish failed: Too many uploads, try again later",
    );
    expect(windowOpen).not.toHaveBeenCalled();
    expect(onClose).not.toHaveBeenCalled();

    const retry = screen.getByTestId("share-static-notebook-button");
    expect(retry).toHaveTextContent("Try again");
    expect(retry).toBeEnabled();
    fireEvent.click(retry);

    expect(await screen.findByTestId("open-claim-page-link")).toHaveAttribute(
      "href",
      CLAIM_URL,
    );
  });

  it("disables both buttons while staging", async () => {
    let resolveStage: (url: string) => void = () => undefined;
    stageForPublishMock.mockImplementation(
      () =>
        new Promise<string>((resolve) => {
          resolveStage = resolve;
        }),
    );
    renderModal();

    fireEvent.click(screen.getByTestId("share-static-notebook-button"));

    await waitFor(() => {
      expect(screen.getByTestId("share-static-notebook-button")).toBeDisabled();
    });
    expect(
      screen.getByTestId("cancel-share-static-notebook-button"),
    ).toBeDisabled();

    resolveStage(CLAIM_URL);
    await screen.findByTestId("open-claim-page-link");
  });
});
