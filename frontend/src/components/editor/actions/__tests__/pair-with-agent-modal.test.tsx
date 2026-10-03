/* Copyright 2026 Marimo. All rights reserved. */

import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { Provider } from "jotai";
import type React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { PAIR_PREVIEW } from "@/__tests__/fixtures/pair-preview";
import { Dialog } from "@/components/ui/dialog";
import { TooltipProvider } from "@/components/ui/tooltip";
import { pairPreviewAtom } from "@/core/config/pair";
import {
  type StableSessionId,
  stableSessionIdAtom,
} from "@/core/kernel/session";
import { filenameAtom } from "@/core/saving/file-state";
import {
  DEFAULT_RUNTIME_CONFIG,
  runtimeConfigAtom,
} from "@/core/runtime/config";
import { store } from "@/core/state/jotai";
import { PairWithAgentModal } from "../pair-with-agent-modal";
import { copyToClipboard } from "@/utils/copy";

vi.mock("@/utils/copy", () => ({
  copyToClipboard: vi.fn().mockResolvedValue(undefined),
}));

function wrapper({ children }: { children: React.ReactNode }) {
  return (
    <Provider store={store}>
      <TooltipProvider>
        <Dialog open={true}>{children}</Dialog>
      </TooltipProvider>
    </Provider>
  );
}

const STABLE_ID = "sess-stable-1" as StableSessionId;

describe("PairWithAgentModal", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    store.set(pairPreviewAtom, PAIR_PREVIEW);
    store.set(stableSessionIdAtom, STABLE_ID);
    store.set(filenameAtom, "/project/my notebook.py");
    store.set(runtimeConfigAtom, {
      ...DEFAULT_RUNTIME_CONFIG,
      url: "http://localhost:8000",
    });
    window.history.replaceState({}, "", "/?file=notebook.py");
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response(JSON.stringify({ token: null }))),
    );
  });

  afterEach(() => {
    store.set(pairPreviewAtom, undefined);
    store.set(stableSessionIdAtom, null);
    store.set(filenameAtom, null);
    vi.unstubAllGlobals();
  });

  it.each(["Claude", "Codex", "OpenCode", "Prompt"])(
    "omits skill installation and targets the stable session in %s preview",
    async (tab) => {
      await act(async () => {
        render(<PairWithAgentModal onClose={vi.fn()} />, { wrapper });
      });
      fireEvent.mouseDown(screen.getByRole("tab", { name: tab }), {
        button: 0,
        ctrlKey: false,
      });

      const panel = screen.getByRole("tabpanel");
      expect(within(panel).queryAllByText(/skill/i)).toEqual([]);
      expect(panel).toHaveTextContent(STABLE_ID);
      expect(panel).not.toHaveTextContent("--file");
      expect(panel).not.toHaveTextContent("File:");
      expect(panel).not.toHaveTextContent("notebook.py");
      expect(panel).toHaveTextContent(
        tab === "Prompt" ? "1. Copy this prompt" : "1. Run in your terminal",
      );
      fireEvent.click(
        within(panel).getByRole("button", {
          name: tab === "Prompt" ? "Copy prompt" : "Copy command",
        }),
      );
      await waitFor(() => expect(copyToClipboard).toHaveBeenCalledOnce());
      const copied = vi.mocked(copyToClipboard).mock.calls[0][0];
      expect(copied).toContain(STABLE_ID);
      expect(copied).not.toContain("notebook.py");
    },
  );

  it.each(["Claude", "Prompt"])(
    "omits the session in %s preview before kernel-ready arrives",
    async (tab) => {
      store.set(stableSessionIdAtom, null);
      await act(async () => {
        render(<PairWithAgentModal onClose={vi.fn()} />, { wrapper });
      });
      fireEvent.mouseDown(screen.getByRole("tab", { name: tab }), {
        button: 0,
        ctrlKey: false,
      });

      const panel = screen.getByRole("tabpanel");
      expect(panel).not.toHaveTextContent("--session");
      expect(panel).not.toHaveTextContent("Session:");
      expect(panel).toHaveTextContent("http://localhost:8000");
    },
  );

  it.each(["Claude", "Codex", "OpenCode", "Prompt"])(
    "preserves the %s skill flow without preview configuration",
    async (tab) => {
      store.set(pairPreviewAtom, undefined);
      window.history.replaceState({}, "", "/");
      await act(async () => {
        render(<PairWithAgentModal onClose={vi.fn()} />, { wrapper });
      });
      fireEvent.mouseDown(screen.getByRole("tab", { name: tab }), {
        button: 0,
        ctrlKey: false,
      });

      const panel = screen.getByRole("tabpanel");
      expect(
        within(panel).getByText("npx skills add marimo-team/marimo-pair"),
      ).toBeVisible();
      expect(panel).not.toHaveTextContent(STABLE_ID);
      expect(panel).not.toHaveTextContent("--file");
      expect(panel).not.toHaveTextContent("MARIMO_PAIR_NEXT");
      expect(panel).not.toHaveTextContent("/project/my notebook.py");
      expect(panel).toHaveTextContent(
        tab === "Prompt" ? "2. Copy this prompt" : "2. Run in your terminal",
      );
    },
  );

  it.each([true, false])(
    "masks the raw token but copies it intact (preview=%s)",
    async (preview) => {
      store.set(pairPreviewAtom, preview ? PAIR_PREVIEW : undefined);
      vi.mocked(fetch).mockResolvedValue(
        new Response(JSON.stringify({ token: "secret-token" })),
      );
      await act(async () => {
        render(<PairWithAgentModal onClose={vi.fn()} />, { wrapper });
      });
      fireEvent.mouseDown(screen.getByRole("tab", { name: "Prompt" }), {
        button: 0,
        ctrlKey: false,
      });

      const panel = screen.getByRole("tabpanel");
      expect(panel).toHaveTextContent("********oken");
      expect(panel).not.toHaveTextContent("secret-token");
      fireEvent.click(
        within(panel).getByRole("button", { name: "Copy prompt" }),
      );
      await waitFor(() => expect(copyToClipboard).toHaveBeenCalledOnce());
      expect(vi.mocked(copyToClipboard).mock.calls[0][0]).toContain(
        preview ? "export MARIMO_TOKEN=secret-token" : "--token secret-token",
      );
      expect(vi.mocked(copyToClipboard).mock.calls[0][0]).not.toContain(
        "********oken",
      );
    },
  );

  it("copies a preview terminal command without the token and lets the user copy the token separately", async () => {
    vi.mocked(fetch).mockResolvedValue(
      new Response(JSON.stringify({ token: "secret-token" })),
    );
    await act(async () => {
      render(<PairWithAgentModal onClose={vi.fn()} />, { wrapper });
    });

    const panel = screen.getByRole("tabpanel");
    expect(panel).toHaveTextContent("2. Paste when prompted for a token");
    expect(panel).not.toHaveTextContent("secret-token");
    fireEvent.click(
      within(panel).getByRole("button", { name: "Copy command" }),
    );
    await waitFor(() =>
      expect(copyToClipboard).toHaveBeenCalledWith(
        String.raw`claude "$(MARIMO_PAIR_NEXT=1 uvx marimo@latest pair prompt \
  --url http://localhost:8000/ \
  --session ${STABLE_ID} \
  --with-token)"`,
      ),
    );
    fireEvent.click(within(panel).getByRole("button", { name: "Copy token" }));
    await waitFor(() =>
      expect(copyToClipboard).toHaveBeenLastCalledWith("secret-token"),
    );
  });
});
