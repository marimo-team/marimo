/* Copyright 2024 Marimo. All rights reserved. */
import { describe, it, expect } from "vitest";
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
});
