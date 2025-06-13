/* Copyright 2024 Marimo. All rights reserved. */

import type { Match, ParamData } from "path-to-regexp";
import { describe, expect, it } from "vitest";
import { TinyRouter } from "../routes";

describe("TinyRouter.match", () => {
  it("should return the correct match and template for a given location", () => {
    const templates = ["/path1", "/path2"];
    const router = new TinyRouter(templates);

    const location1 = { hash: "", pathname: "/path1" } as Location;
    const location2 = { hash: "", pathname: "/path2" } as Location;

    expect(router.match(location1)).toEqual([expect.any(Object), "/path1"]);
    expect(router.match(location2)).toEqual([expect.any(Object), "/path2"]);
  });

  it("should return false if no match is found", () => {
    const templates = ["/path1", "/path2"];
    const router = new TinyRouter(templates);

    const location = { hash: "", pathname: "/path3" } as Location;

    expect(router.match(location)).toBe(false);
  });

  it("should return the correct match for hash locations", () => {
    const templates = ["#/path1", "#/path2"];
    const router = new TinyRouter(templates);

    const location = { hash: "#/path1", pathname: "" } as Location;

    expect(router.match(location)).toEqual([expect.any(Object), "#/path1"]);
  });

  it("order should matter for nested routes", () => {
    const templates = ["/path1", "/path1/nested"];
    const router = new TinyRouter(templates);

    const location = { hash: "", pathname: "/path1/nested" } as Location;

    expect(router.match(location)).toEqual([
      expect.any(Object),
      "/path1/nested",
    ]);
  });

  it("should match catch all route", () => {
    const catchAll = "{/*path}"; // this matches CATCH_ALL in routes.py
    const templates = ["/path1", catchAll];
    const router = new TinyRouter(templates);

    let location = { hash: "", pathname: "/anything" } as Location;
    expect(router.match(location)).toEqual([expect.any(Object), "{/*path}"]);

    location = { hash: "", pathname: "/anything/else" } as Location;
    expect(router.match(location)).toEqual([expect.any(Object), "{/*path}"]);

    location = { hash: "", pathname: "/" } as Location;
    expect(router.match(location)).toEqual([expect.any(Object), "{/*path}"]);

    location = { hash: "", pathname: "/path1" } as Location;
    expect(router.match(location)).toEqual([expect.any(Object), "/path1"]);
  });

  it("should match routes with parameters", () => {
    const templates = ["/users/:id", "/posts/:postId/comments"];
    const router = new TinyRouter(templates);

    const location = { hash: "", pathname: "/users/123" } as Location;
    const [match] = router.match(location) as [Match<ParamData>, string];

    expect(match).toMatchInlineSnapshot(`
      {
        "params": {
          "id": "123",
        },
        "path": "/users/123",
      }
    `);
  });

  it("should match routes with multiple parameters", () => {
    const templates = ["/users/:userId/posts/:postId"];
    const router = new TinyRouter(templates);

    const location = { hash: "", pathname: "/users/123/posts/456" } as Location;
    const [match] = router.match(location) as [Match<ParamData>, string];

    expect(match).toMatchInlineSnapshot(`
      {
        "params": {
          "postId": "456",
          "userId": "123",
        },
        "path": "/users/123/posts/456",
      }
    `);
  });

  it("should handle query parameters", () => {
    const templates = ["/search"];
    const router = new TinyRouter(templates);

    const location = {
      hash: "",
      pathname: "/search",
      search: "?q=test&page=2",
    } as Location;

    const [match] = router.match(location) as [Match<ParamData>, string];
    expect(match).toBeDefined();
  });

  it("should match exact paths with trailing slashes", () => {
    const templates = ["/path1", "/path2/"];
    const router = new TinyRouter(templates);

    const location1 = { hash: "", pathname: "/path1/" } as Location;
    const location2 = { hash: "", pathname: "/path2" } as Location;

    expect(router.match(location1)).toMatchInlineSnapshot(`
      [
        {
          "params": {},
          "path": "/path1/",
        },
        "/path1",
      ]
    `);
    expect(router.match(location2)).toBe(false);
  });
});
