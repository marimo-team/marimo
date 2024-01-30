/* Copyright 2024 Marimo. All rights reserved. */
import { expect, describe, it } from "vitest";
import { Milliseconds, Time, Seconds } from "../time";

describe("Time class", () => {
  describe("fromMilliseconds", () => {
    it("should create a Time instance from milliseconds", () => {
      const ms: Milliseconds = 1000 as Milliseconds;
      const time = Time.fromMilliseconds(ms);
      expect(time).toBeInstanceOf(Time);
      expect(time.toMilliseconds()).toBe(ms);
    });

    it("should return null when null is passed", () => {
      const time = Time.fromMilliseconds(null);
      expect(time).toBeNull();
    });
  });

  describe("fromSeconds", () => {
    it("should create a Time instance from seconds", () => {
      const s: Seconds = 1 as Seconds;
      const time = Time.fromSeconds(s);
      expect(time).toBeInstanceOf(Time);
      expect(time.toSeconds()).toBe(s);
    });

    it("should return null when null is passed", () => {
      const time = Time.fromSeconds(null);
      expect(time).toBeNull();
    });
  });

  describe("now", () => {
    it("should create a Time instance representing the current time", () => {
      const before = Date.now();
      const time = Time.now();
      const after = Date.now();
      expect(time.toMilliseconds()).toBeGreaterThanOrEqual(before);
      expect(time.toMilliseconds()).toBeLessThanOrEqual(after);
    });
  });

  describe("toMilliseconds", () => {
    it("should return the time in milliseconds", () => {
      const ms = 1500 as Milliseconds;
      // @ts-expect-error Directly using the private constructor for testing
      const time = new Time(ms);
      expect(time.toMilliseconds()).toBe(ms);
    });
  });

  describe("toSeconds", () => {
    it("should return the time in seconds", () => {
      const ms = 3000 as Milliseconds;
      // @ts-expect-error Directly using the private constructor for testing
      const time = new Time(ms);
      expect(time.toSeconds()).toBe(3);
    });
  });
});
