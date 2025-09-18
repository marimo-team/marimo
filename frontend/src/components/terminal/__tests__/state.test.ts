/* Copyright 2024 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import { exportedForTesting } from "../state";

const { reducer, initialState } = exportedForTesting;

describe("terminal state", () => {
  describe("initialState", () => {
    it("should return initial state with empty pendingCommands and isReady false", () => {
      const state = initialState();
      expect(state).toEqual({
        pendingCommands: [],
        isReady: false,
      });
    });
  });

  describe("reducer", () => {
    it("should add a command to pendingCommands", () => {
      const state = initialState();
      const text = "ls -la";

      const newState = reducer(state, { type: "addCommand", payload: text });

      expect(newState.pendingCommands).toHaveLength(1);
      expect(newState.pendingCommands[0]).toMatchObject({
        text: "ls -la",
        timestamp: expect.any(Number),
      });
      expect(newState.pendingCommands[0].id).toBeDefined();
      expect(newState.isReady).toBe(false);
    });

    it("should add multiple commands to pendingCommands", () => {
      const state = initialState();

      let newState = reducer(state, { type: "addCommand", payload: "ls -la" });
      newState = reducer(newState, { type: "addCommand", payload: "cd /home" });
      newState = reducer(newState, { type: "addCommand", payload: "pwd" });

      expect(newState.pendingCommands).toHaveLength(3);
      expect(newState.pendingCommands[0].text).toBe("ls -la");
      expect(newState.pendingCommands[1].text).toBe("cd /home");
      expect(newState.pendingCommands[2].text).toBe("pwd");
    });

    it("should remove a command by id", () => {
      const state = initialState();

      let newState = reducer(state, { type: "addCommand", payload: "ls -la" });
      newState = reducer(newState, { type: "addCommand", payload: "cd /home" });
      newState = reducer(newState, { type: "addCommand", payload: "pwd" });

      const commandToRemove = newState.pendingCommands[1];
      newState = reducer(newState, {
        type: "removeCommand",
        payload: commandToRemove.id,
      });

      expect(newState.pendingCommands).toHaveLength(2);
      expect(newState.pendingCommands[0].text).toBe("ls -la");
      expect(newState.pendingCommands[1].text).toBe("pwd");
    });

    it("should not remove anything if command id does not exist", () => {
      const state = initialState();

      let newState = reducer(state, { type: "addCommand", payload: "ls -la" });
      newState = reducer(newState, { type: "addCommand", payload: "cd /home" });

      const originalLength = newState.pendingCommands.length;
      newState = reducer(newState, {
        type: "removeCommand",
        payload: "non-existent-id",
      });

      expect(newState.pendingCommands).toHaveLength(originalLength);
    });

    it("should set isReady to true", () => {
      const state = initialState();

      const newState = reducer(state, { type: "setReady", payload: true });

      expect(newState.isReady).toBe(true);
      expect(newState.pendingCommands).toEqual([]);
    });

    it("should set isReady to false", () => {
      const state = { ...initialState(), isReady: true };

      const newState = reducer(state, { type: "setReady", payload: false });

      expect(newState.isReady).toBe(false);
    });

    it("should clear all pending commands", () => {
      const state = initialState();

      let newState = reducer(state, { type: "addCommand", payload: "ls -la" });
      newState = reducer(newState, { type: "addCommand", payload: "cd /home" });
      newState = reducer(newState, { type: "addCommand", payload: "pwd" });

      expect(newState.pendingCommands).toHaveLength(3);

      newState = reducer(newState, {
        type: "clearCommands",
        payload: undefined,
      });

      expect(newState.pendingCommands).toHaveLength(0);
      expect(newState.isReady).toBe(false);
    });

    it("should preserve other state when adding commands", () => {
      const state = { ...initialState(), isReady: true };

      const newState = reducer(state, {
        type: "addCommand",
        payload: "ls -la",
      });

      expect(newState.isReady).toBe(true);
      expect(newState.pendingCommands).toHaveLength(1);
    });

    it("should preserve other state when removing commands", () => {
      const state = { ...initialState(), isReady: true };

      let newState = reducer(state, { type: "addCommand", payload: "ls -la" });
      newState = reducer(newState, {
        type: "removeCommand",
        payload: newState.pendingCommands[0].id,
      });

      expect(newState.isReady).toBe(true);
      expect(newState.pendingCommands).toHaveLength(0);
    });

    it("should preserve other state when setting ready", () => {
      const state = initialState();

      let newState = reducer(state, { type: "addCommand", payload: "ls -la" });
      newState = reducer(newState, { type: "addCommand", payload: "cd /home" });
      newState = reducer(newState, { type: "setReady", payload: true });

      expect(newState.isReady).toBe(true);
      expect(newState.pendingCommands).toHaveLength(2);
    });

    it("should preserve other state when clearing commands", () => {
      const state = { ...initialState(), isReady: true };

      let newState = reducer(state, { type: "addCommand", payload: "ls -la" });
      newState = reducer(newState, {
        type: "clearCommands",
        payload: undefined,
      });

      expect(newState.isReady).toBe(true);
      expect(newState.pendingCommands).toHaveLength(0);
    });
  });

  describe("command properties", () => {
    it("should generate unique ids for commands", () => {
      const state = initialState();

      let newState = reducer(state, {
        type: "addCommand",
        payload: "command1",
      });
      newState = reducer(newState, { type: "addCommand", payload: "command2" });

      const ids = newState.pendingCommands.map((cmd) => cmd.id);
      expect(ids[0]).not.toBe(ids[1]);
      expect(ids[0]).toBeDefined();
      expect(ids[1]).toBeDefined();
    });

    it("should set timestamp when adding commands", () => {
      const state = initialState();
      const beforeTime = Date.now();

      const newState = reducer(state, {
        type: "addCommand",
        payload: "ls -la",
      });

      const afterTime = Date.now();
      const command = newState.pendingCommands[0];

      expect(command.timestamp).toBeGreaterThanOrEqual(beforeTime);
      expect(command.timestamp).toBeLessThanOrEqual(afterTime);
    });

    it("should preserve text when adding commands", () => {
      const state = initialState();
      const text = "echo 'Hello World'";

      const newState = reducer(state, { type: "addCommand", payload: text });

      expect(newState.pendingCommands[0].text).toBe(text);
    });
  });
});
