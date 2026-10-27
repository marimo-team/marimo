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
import { PAIR_CONFIG } from "@/__tests__/fixtures/pair-config";
import { Dialog } from "@/components/ui/dialog";
import { TooltipProvider } from "@/components/ui/tooltip";
import { pairConfigAtom } from "@/core/config/pair";
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
import { Deferred } from "@/utils/Deferred";
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
const NOTEBOOK_ID = "nb-one";
function responseFor(url: string | URL | Request, token: string | null = null) {
  return Promise.resolve(
    new Response(
      JSON.stringify(
        String(url).endsWith("/api/sessions")
          ? { one: { session_id: STABLE_ID, notebook_id: NOTEBOOK_ID } }
          : { token },
      ),
      { headers: { "Content-Type": "application/json" } },
    ),
  );
}

describe("PairWithAgentModal", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    store.set(pairConfigAtom, PAIR_CONFIG);
    store.set(stableSessionIdAtom, STABLE_ID);
    store.set(filenameAtom, "/project/my notebook.py");
    store.set(runtimeConfigAtom, {
      ...DEFAULT_RUNTIME_CONFIG,
      url: "http://localhost:8000",
    });
    window.history.replaceState({}, "", "/?file=notebook.py");
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation((url) => responseFor(url)),
    );
  });

  afterEach(() => {
    store.set(pairConfigAtom, undefined);
    store.set(stableSessionIdAtom, null);
    store.set(filenameAtom, null);
    vi.unstubAllGlobals();
  });

  it.each(["Claude", "Codex", "OpenCode", "Prompt"])(
    "targets the verified host Notebook in %s",
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
      expect(panel).toHaveTextContent(NOTEBOOK_ID);
      expect(panel).not.toHaveTextContent("--file");
      expect(panel).not.toHaveTextContent("File:");
      expect(panel).not.toHaveTextContent("notebook.py");
      expect(
        panel.textContent?.includes("Agent connections require OpenCode 2.x"),
      ).toBe(tab === "OpenCode");
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
      expect(copied).toContain(NOTEBOOK_ID);
      expect(copied).not.toContain("notebook.py");
      expect(copied).not.toContain(STABLE_ID);
      expect(panel).not.toHaveTextContent(STABLE_ID);
    },
  );

  it.each(["Claude", "Prompt"])(
    "waits for kernel-ready before copying the %s target",
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
      expect(panel).not.toHaveTextContent("--notebook");
      expect(panel).not.toHaveTextContent("Notebook:");
      expect(panel).toHaveTextContent("http://localhost:8000");
      expect(
        within(panel).getByRole("button", {
          name: tab === "Prompt" ? "Copy prompt" : "Copy command",
        }),
      ).toBeDisabled();
    },
  );

  it.each(["Claude", "Codex", "OpenCode", "Prompt"])(
    "uses the editor CLI in %s when host is disabled",
    async (tab) => {
      store.set(pairConfigAtom, { ...PAIR_CONFIG, hostEnabled: false });
      await act(async () => {
        render(<PairWithAgentModal onClose={vi.fn()} />, { wrapper });
      });
      fireEvent.mouseDown(screen.getByRole("tab", { name: tab }), {
        button: 0,
        ctrlKey: false,
      });
      const panel = screen.getByRole("tabpanel");
      expect(panel).toHaveTextContent(STABLE_ID);
      expect(panel).not.toHaveTextContent(NOTEBOOK_ID);
      expect(panel).not.toHaveTextContent("skill");
      expect(panel).not.toHaveTextContent("Agent connections require");
      expect(panel).not.toHaveTextContent("MARIMO_PAIR_NEXT");
      fireEvent.click(
        within(panel).getByRole("button", {
          name: tab === "Prompt" ? "Copy prompt" : "Copy command",
        }),
      );
      await waitFor(() => expect(copyToClipboard).toHaveBeenCalledOnce());
      expect(vi.mocked(copyToClipboard).mock.calls[0][0]).toContain(STABLE_ID);
      expect(
        vi
          .mocked(fetch)
          .mock.calls.some(([url]) => String(url).endsWith("/api/sessions")),
      ).toBe(false);
    },
  );

  it.each([true, false])(
    "masks the raw token but copies it intact (host mode=%s)",
    async (hostEnabled) => {
      store.set(pairConfigAtom, { ...PAIR_CONFIG, hostEnabled });
      vi.mocked(fetch).mockImplementation((url) =>
        responseFor(url, "secret-token"),
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
        "export MARIMO_TOKEN=secret-token",
      );
      expect(vi.mocked(copyToClipboard).mock.calls[0][0]).not.toContain(
        "********oken",
      );
    },
  );

  it("uses the CLI when an older server omits Pair configuration", async () => {
    store.set(pairConfigAtom, undefined);
    await act(async () => {
      render(<PairWithAgentModal onClose={vi.fn()} />, { wrapper });
    });
    const panel = screen.getByRole("tabpanel");
    expect(panel).toHaveTextContent(`--session ${STABLE_ID}`);
    expect(panel).not.toHaveTextContent("skill");
    expect(screen.getByRole("button", { name: "Copy command" })).toBeEnabled();
  });

  it("ignores a previous Session's late Notebook lookup", async () => {
    const previous = new Deferred<Response>();
    const nextId = "sess-next" as StableSessionId;
    let lookups = 0;
    vi.mocked(fetch).mockImplementation((url) => {
      if (!String(url).endsWith("/api/sessions")) {
        return responseFor(url);
      }
      if (lookups++ === 0) {
        return previous.promise;
      }
      return Promise.resolve(
        new Response(
          JSON.stringify({
            next: { session_id: nextId, notebook_id: "nb-next" },
          }),
          { headers: { "Content-Type": "application/json" } },
        ),
      );
    });
    await act(async () => {
      render(<PairWithAgentModal onClose={vi.fn()} />, { wrapper });
    });
    await act(async () => store.set(stableSessionIdAtom, nextId));
    expect(screen.getByRole("tabpanel")).toHaveTextContent("nb-next");
    await act(async () =>
      previous.resolve(
        new Response(
          JSON.stringify({
            previous: { session_id: STABLE_ID, notebook_id: NOTEBOOK_ID },
          }),
          { headers: { "Content-Type": "application/json" } },
        ),
      ),
    );
    expect(screen.getByRole("tabpanel")).toHaveTextContent("nb-next");
    expect(screen.getByRole("tabpanel")).not.toHaveTextContent(NOTEBOOK_ID);
  });

  it("disables target copying while a new Session's Notebook is unverified", async () => {
    await act(async () => {
      render(<PairWithAgentModal onClose={vi.fn()} />, { wrapper });
    });
    expect(screen.getByRole("tabpanel")).toHaveTextContent(NOTEBOOK_ID);
    const pending = new Deferred<Response>();
    vi.mocked(fetch).mockImplementation((url) =>
      String(url).endsWith("/api/sessions")
        ? pending.promise
        : responseFor(url),
    );
    const nextId = "sess-stable-2" as StableSessionId;
    act(() => store.set(stableSessionIdAtom, nextId));
    expect(screen.getByRole("button", { name: "Copy command" })).toBeDisabled();
    expect(screen.getByRole("tabpanel")).not.toHaveTextContent(NOTEBOOK_ID);
    fireEvent.click(screen.getByRole("button", { name: "Copy command" }));
    expect(copyToClipboard).not.toHaveBeenCalled();
    await act(async () =>
      pending.resolve(
        new Response(
          JSON.stringify({
            next: { session_id: nextId, notebook_id: "nb-two" },
          }),
          { headers: { "Content-Type": "application/json" } },
        ),
      ),
    );
    expect(screen.getByRole("button", { name: "Copy command" })).toBeEnabled();
    fireEvent.click(screen.getByRole("button", { name: "Copy command" }));
    await waitFor(() => expect(copyToClipboard).toHaveBeenCalledOnce());
    expect(vi.mocked(copyToClipboard).mock.calls[0][0]).toContain("nb-two");
    expect(vi.mocked(copyToClipboard).mock.calls[0][0]).not.toContain(nextId);
  });

  it("uses the Session after verifying that a notebook is unsaved", async () => {
    vi.mocked(fetch).mockImplementation((url) =>
      String(url).endsWith("/api/sessions")
        ? Promise.resolve(
            new Response(
              JSON.stringify({
                one: { session_id: STABLE_ID, notebook_id: null },
              }),
              { headers: { "Content-Type": "application/json" } },
            ),
          )
        : responseFor(url),
    );
    await act(async () => {
      render(<PairWithAgentModal onClose={vi.fn()} />, { wrapper });
    });
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Copy command" })).toBeEnabled();
    expect(screen.getByRole("tabpanel")).toHaveTextContent(
      `--session ${STABLE_ID}`,
    );
    expect(screen.getByRole("tabpanel")).not.toHaveTextContent("--notebook");
  });

  it("reverifies the target when host mode is enabled again for the same Session", async () => {
    await act(async () => {
      render(<PairWithAgentModal onClose={vi.fn()} />, { wrapper });
    });
    expect(screen.getByRole("tabpanel")).toHaveTextContent(NOTEBOOK_ID);
    act(() =>
      store.set(pairConfigAtom, { ...PAIR_CONFIG, hostEnabled: false }),
    );

    const pending = new Deferred<Response>();
    vi.mocked(fetch).mockImplementation((url) =>
      String(url).endsWith("/api/sessions")
        ? pending.promise
        : responseFor(url),
    );
    act(() => store.set(pairConfigAtom, PAIR_CONFIG));
    expect(screen.getByRole("button", { name: "Copy command" })).toBeDisabled();
    expect(screen.getByRole("tabpanel")).not.toHaveTextContent(NOTEBOOK_ID);

    await act(async () => pending.resolve(await responseFor("/api/sessions")));
    expect(screen.getByRole("button", { name: "Copy command" })).toBeEnabled();
    expect(screen.getByRole("tabpanel")).toHaveTextContent(NOTEBOOK_ID);
  });

  it("keeps copying disabled when Notebook verification fails", async () => {
    vi.mocked(fetch).mockImplementation((url) =>
      String(url).endsWith("/api/sessions")
        ? Promise.reject(new Error("offline"))
        : responseFor(url),
    );
    await act(async () => {
      render(<PairWithAgentModal onClose={vi.fn()} />, { wrapper });
    });
    expect(screen.getByRole("status")).toHaveTextContent(
      "Could not verify this notebook",
    );
    expect(screen.getByRole("button", { name: "Copy command" })).toBeDisabled();
  });

  it("copies a host mode terminal command without the token and lets the user copy the token separately", async () => {
    vi.mocked(fetch).mockImplementation((url) =>
      responseFor(url, "secret-token"),
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
        String.raw`claude "$(uvx marimo@latest pair prompt \
  --url http://localhost:8000/ \
  --notebook ${NOTEBOOK_ID} \
  --with-token)"`,
      ),
    );
    fireEvent.click(within(panel).getByRole("button", { name: "Copy token" }));
    await waitFor(() =>
      expect(copyToClipboard).toHaveBeenLastCalledWith("secret-token"),
    );
  });
});
