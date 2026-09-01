/* Copyright 2026 Marimo. All rights reserved. */

import { beforeEach, describe, expect, it, vi } from "vitest";
import { HTTPError } from "@/utils/errors";
import { API } from "../api";

// Mock fetch globally
const mockFetch = vi.fn();
global.fetch = mockFetch;

// Default mock for getRuntimeManager
let baseUrl = "http://localhost:8000";
vi.mock("@/core/runtime/config", () => ({
  getRuntimeManager: () => ({
    get httpURL() {
      return new URL(baseUrl);
    },
    headers: () => ({}),
  }),
}));

describe("API", () => {
  beforeEach(() => {
    mockFetch.mockReset();
    baseUrl = "http://localhost:8000";
  });

  it("API.post calls fetch with POST and correct URL", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      headers: { get: () => "application/json" },
      json: () => Promise.resolve({ ok: true }),
    });
    await API.post("/foo", { bar: 1 });
    expect(mockFetch).toHaveBeenCalledWith(
      "http://localhost:8000/api/foo",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("API.get calls fetch with GET and correct URL", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      headers: { get: () => "application/json" },
      json: () => Promise.resolve({ ok: true }),
    });
    await API.get("/bar");
    expect(mockFetch).toHaveBeenCalledWith(
      "http://localhost:8000/api/bar",
      expect.objectContaining({ method: "GET" }),
    );
  });

  it("API.post handles base URL with path correctly", async () => {
    baseUrl = "http://example.com/e";
    mockFetch.mockResolvedValue({
      ok: true,
      headers: { get: () => "application/json" },
      json: () => Promise.resolve({ ok: true }),
    });
    await API.post("/foo", { bar: 1 });
    expect(mockFetch).toHaveBeenCalledWith(
      "http://example.com/e/api/foo",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("API.post handles base URL with trailing slash correctly", async () => {
    baseUrl = "http://example.com/e/";
    mockFetch.mockResolvedValue({
      ok: true,
      headers: { get: () => "application/json" },
      json: () => Promise.resolve({ ok: true }),
    });
    await API.post("/foo", { bar: 1 });
    expect(mockFetch).toHaveBeenCalledWith(
      "http://example.com/e/api/foo",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("openapi-client error rejects with HTTPError carrying the status", async () => {
    const body = { detail: "This connection is read-only for this action." };
    await expect(
      API.handleResponseReturnNull({
        error: body,
        response: { status: 403, statusText: "Forbidden" } as Response,
      }),
    ).rejects.toMatchObject({ status: 403, cause: body });
    await expect(
      API.handleResponseReturnNull({
        error: body,
        response: { status: 403, statusText: "Forbidden" } as Response,
      }),
    ).rejects.toBeInstanceOf(HTTPError);
  });

  it("preserves export metadata from response headers", async () => {
    const response = new Response("markdown", {
      headers: {
        "Content-Disposition":
          "attachment; filename*=UTF-8''r%C3%A9sum%C3%A9.qmd",
        "Content-Type": "text/plain; charset=utf-8",
      },
    });

    await expect(
      API.handleExportResponse(
        { data: "markdown", response },
        { defaultFilename: "download.md" },
      ),
    ).resolves.toEqual({
      contents: "markdown",
      filename: "résumé.qmd",
      mediaType: "text/plain; charset=utf-8",
    });
  });

  it("parses quoted Content-Disposition filenames", async () => {
    const response = new Response("html", {
      headers: {
        "Content-Disposition": 'inline; filename="notebook.html"',
        "Content-Type": "text/html; charset=utf-8",
      },
    });

    await expect(
      API.handleExportResponse(
        { data: "html", response },
        { defaultFilename: "download.html" },
      ),
    ).resolves.toEqual({
      contents: "html",
      filename: "notebook.html",
      mediaType: "text/html; charset=utf-8",
    });
  });

  it("parses unquoted Content-Disposition filenames", async () => {
    const response = new Response("pdf", {
      headers: {
        "Content-Disposition": "attachment; filename=notebook.pdf",
        "Content-Type": "application/pdf",
      },
    });

    await expect(
      API.handleExportResponse(
        { data: "pdf", response },
        { defaultFilename: "download.pdf" },
      ),
    ).resolves.toEqual({
      contents: "pdf",
      filename: "notebook.pdf",
      mediaType: "application/pdf",
    });
  });

  it("prefers RFC 5987 filenames over quoted fallbacks", async () => {
    const response = new Response("markdown", {
      headers: {
        "Content-Disposition":
          "attachment; filename=\"wrong.md\"; filename*=UTF-8''notebook.md",
        "Content-Type": "text/plain; charset=utf-8",
      },
    });

    await expect(
      API.handleExportResponse(
        { data: "markdown", response },
        { defaultFilename: "download.md" },
      ),
    ).resolves.toEqual({
      contents: "markdown",
      filename: "notebook.md",
      mediaType: "text/plain; charset=utf-8",
    });
  });

  it("falls back to a default filename when headers are missing", async () => {
    const response = new Response("markdown", {
      headers: {
        "Content-Type": "text/plain; charset=utf-8",
      },
    });

    await expect(
      API.handleExportResponse(
        { data: "markdown", response },
        { defaultFilename: "download.md" },
      ),
    ).resolves.toEqual({
      contents: "markdown",
      filename: "download.md",
      mediaType: "text/plain; charset=utf-8",
    });
  });

  it("falls back to a default filename when Content-Disposition is unparsable", async () => {
    const response = new Response("markdown", {
      headers: {
        "Content-Disposition": "attachment",
        "Content-Type": "text/plain; charset=utf-8",
      },
    });

    await expect(
      API.handleExportResponse(
        { data: "markdown", response },
        { defaultFilename: "download.md" },
      ),
    ).resolves.toEqual({
      contents: "markdown",
      filename: "download.md",
      mediaType: "text/plain; charset=utf-8",
    });
  });

  it("falls back to a default filename when RFC 5987 encoding is malformed", async () => {
    const response = new Response("markdown", {
      headers: {
        "Content-Disposition": "attachment; filename*=UTF-8''%E0%A4%A",
        "Content-Type": "text/plain; charset=utf-8",
      },
    });

    await expect(
      API.handleExportResponse(
        { data: "markdown", response },
        { defaultFilename: "download.md" },
      ),
    ).resolves.toEqual({
      contents: "markdown",
      filename: "download.md",
      mediaType: "text/plain; charset=utf-8",
    });
  });

  it("rejects export responses without a media type", async () => {
    await expect(
      API.handleExportResponse(
        {
          data: "markdown",
          response: new Response(null, {
            headers: {
              "Content-Disposition": "attachment; filename*=UTF-8''notebook.md",
            },
          }),
        },
        { defaultFilename: "download.md" },
      ),
    ).rejects.toThrow("Export response is missing a media type");
  });
});
