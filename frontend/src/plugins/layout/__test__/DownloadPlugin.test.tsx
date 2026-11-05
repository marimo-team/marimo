/* Copyright 2026 Marimo. All rights reserved. */

import {
  act,
  cleanup,
  fireEvent,
  render,
  waitFor,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { Mocks } from "@/__mocks__/common";
import { toast } from "@/components/ui/use-toast";
import { assertExists } from "@/utils/assertExists";
import { Deferred } from "@/utils/Deferred";
import { registerReactComponent } from "../../core/registerReactComponent";
import { sanitizeHtml } from "../../core/sanitize-html";
import { DownloadPlugin } from "../DownloadPlugin";

vi.mock("@/components/ui/use-toast", () => ({ toast: vi.fn() }));
vi.mock("@/utils/Logger", () => ({ Logger: Mocks.quietLogger() }));

type DownloadData = Parameters<typeof DownloadPlugin.render>[0]["data"];
type Load = Parameters<typeof DownloadPlugin.render>[0]["functions"]["load"];

function renderDownload(
  data: Partial<DownloadData> = {},
  load = vi.fn<Load>(),
) {
  const result = render(
    DownloadPlugin.render({
      host: document.createElement("div"),
      value: null,
      setValue: vi.fn(),
      data: DownloadPlugin.validator.parse({
        data: "./@file/123-results.csv",
        filename: "results.csv",
        ...data,
      }),
      functions: { load },
    }),
  );
  const button = result.getByText("Download").closest("a");
  assertExists(button);
  return { ...result, load, button };
}

describe("DownloadPlugin", () => {
  const downloads: { href: string | null; filename: string | null }[] = [];

  beforeEach(() => {
    downloads.length = 0;
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (
      this: HTMLAnchorElement,
    ) {
      downloads.push({
        href: this.getAttribute("href"),
        filename: this.getAttribute("download"),
      });
    });
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
    vi.clearAllMocks();
  });

  it("downloads immediately without calling load", () => {
    const { button, load } = renderDownload();
    fireEvent.click(button);

    expect(downloads).toEqual([
      { href: "./@file/123-results.csv", filename: "results.csv" },
    ]);
    expect(load).not.toHaveBeenCalled();
  });

  it.each([
    { data: "data:text/plain,hello", filename: "loaded.txt" },
    { data: "", filename: "renamed.csv" },
    { data: "data:text/plain,hello", filename: null },
  ])("downloads lazy data with metadata fallbacks: %j", async (loadedData) => {
    const load = vi.fn<Load>().mockResolvedValue(loadedData);
    const { button } = renderDownload({ lazy: true }, load);
    fireEvent.click(button);

    await waitFor(() => {
      expect(downloads).toEqual([
        {
          href: loadedData.data || "./@file/123-results.csv",
          filename: loadedData.filename ?? "results.csv",
        },
      ]);
    });
    expect(load).toHaveBeenCalledExactlyOnceWith({});
  });

  it.each([false, true])("ignores disabled clicks (lazy=%s)", (lazy) => {
    const { button, load } = renderDownload({ disabled: true, lazy });
    fireEvent.click(button);
    expect(downloads).toEqual([]);
    expect(load).not.toHaveBeenCalled();
    expect(toast).not.toHaveBeenCalled();
  });

  it.each([false, true])(
    "handles an unsupported URL (lazy=%s)",
    async (lazy) => {
      const data = "java\nscript:alert(1)";
      const load = vi.fn<Load>().mockResolvedValue({ data });
      const { button } = renderDownload({ data, lazy }, load);
      expect(button.hasAttribute("href")).toBe(false);
      fireEvent.click(button);

      await waitFor(() => {
        expect(toast).toHaveBeenCalledWith({
          title: "Failed to download",
          description: "Please try again.",
        });
      });
      expect(downloads).toEqual([]);
    },
  );

  it("validates the lazy response even when the initial URL is valid", async () => {
    const load = vi
      .fn<Load>()
      .mockResolvedValue({ data: "javascript:alert(1)" });
    const { button } = renderDownload({ lazy: true }, load);
    fireEvent.click(button);

    await waitFor(() => expect(toast).toHaveBeenCalledOnce());
    expect(downloads).toEqual([]);
  });

  it("validates the fallback URL when lazy loading only returns a filename", async () => {
    const load = vi
      .fn<Load>()
      .mockResolvedValue({ data: "", filename: "file.txt" });
    const { button } = renderDownload(
      { data: "javascript:alert(1)", lazy: true },
      load,
    );
    fireEvent.click(button);

    await waitFor(() => expect(toast).toHaveBeenCalledOnce());
    expect(downloads).toEqual([]);
  });

  it("ignores clicks while loading and allows retry after a failed load", async () => {
    const pendingLoad = new Deferred<Awaited<ReturnType<Load>>>();
    const load = vi
      .fn<Load>()
      .mockReturnValueOnce(pendingLoad.promise)
      .mockResolvedValue({ data: "data:text/plain,retry" });
    const { button } = renderDownload({ data: "", lazy: true }, load);
    fireEvent.click(button);
    fireEvent.click(button);
    expect(load).toHaveBeenCalledOnce();

    await act(async () => pendingLoad.reject(new Error("Load failed")));
    expect(toast).toHaveBeenCalledOnce();
    expect(downloads).toEqual([]);

    fireEvent.click(button);
    await waitFor(() =>
      expect(downloads).toEqual([
        { href: "data:text/plain,retry", filename: "results.csv" },
      ]),
    );
    expect(load).toHaveBeenCalledTimes(2);
  });

  it("rejects an unsupported URL restored from sanitized output", async () => {
    registerReactComponent(DownloadPlugin);
    const container = document.createElement("div");
    container.innerHTML = sanitizeHtml(
      `<marimo-download data-data='"javascript:alert(1)"' data-initial-value='null' data-disabled='false' data-lazy='false'></marimo-download>`,
    );
    try {
      await act(async () => {
        document.body.append(container);
      });
      const button = container
        .querySelector("marimo-download")
        ?.shadowRoot?.querySelector("a");
      assertExists(button);
      expect(button.hasAttribute("href")).toBe(false);
      fireEvent.click(button);
      expect(toast).toHaveBeenCalledOnce();
      expect(downloads).toEqual([]);
    } finally {
      await act(async () => container.remove());
    }
  });
});
