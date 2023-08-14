/* Copyright 2023 Marimo. All rights reserved. */
import { rest } from "msw";
import { SaveKernelRequest } from "../core/network/types";

export const handlers = [
  // Run
  rest.post("/api/kernel/run/", (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        status: "ok",
      })
    );
  }),

  // Save
  rest.post<SaveKernelRequest>("/api/kernel/save/", async (req, res, ctx) => {
    sessionStorage.setItem(
      "merimo:msw:save",
      JSON.stringify(await req.json<SaveKernelRequest>())
    );

    return res(
      ctx.status(200),
      ctx.json({
        status: "ok",
      })
    );
  }),

  // Instantiate
  rest.post("/api/kernel/instantiate/", (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        status: "ok",
      })
    );
  }),

  // Directory autocomplete
  rest.post("/api/kernel/directory_autocomplete/", (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        status: "ok",
        matches: [],
        files: [],
      })
    );
  }),

  // Rename
  rest.post("/api/kernel/rename/", (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        status: "ok",
      })
    );
  }),

  // Delete
  rest.post("/api/kernel/delete/", (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        status: "ok",
      })
    );
  }),
];
