/* Copyright 2026 Marimo. All rights reserved. */
import { beforeEach, describe, expect, it } from "vitest";
import type { VariableName } from "../../variables/types";
import { exportedForTesting } from "../state";
import type { StorageEntry, StorageNamespace, StorageState } from "../types";

const { initialState, reducer, createActions } = exportedForTesting;

function makeNamespace(
  overrides: Partial<StorageNamespace> & { name: string },
): StorageNamespace {
  return {
    displayName: overrides.displayName ?? overrides.name,
    name: overrides.name,
    protocol: overrides.protocol ?? "s3",
    rootPath: overrides.rootPath ?? "/",
    storageEntries: overrides.storageEntries ?? [],
  };
}

function makeEntry(
  overrides: Partial<StorageEntry> & { path: string },
): StorageEntry {
  return {
    kind: overrides.kind ?? "file",
    lastModified: overrides.lastModified ?? null,
    metadata: overrides.metadata ?? {},
    path: overrides.path,
    size: overrides.size ?? 0,
  };
}

describe("storage state", () => {
  let state: StorageState;

  const actions = createActions((action) => {
    state = reducer(state, action);
  });

  beforeEach(() => {
    state = initialState();
  });

  describe("initialState", () => {
    it("should start with empty namespaces and entries", () => {
      expect(state).toEqual({
        namespaces: [],
        entriesByPath: new Map(),
      });
    });
  });

  describe("setNamespaces", () => {
    it("should add namespaces from an empty state", () => {
      const ns1 = makeNamespace({ name: "my_s3", protocol: "s3" });
      const ns2 = makeNamespace({ name: "my_gcs", protocol: "gcs" });

      actions.setNamespaces({ namespaces: [ns1, ns2] });

      expect(state.namespaces).toEqual([ns1, ns2]);
    });

    it("should merge namespaces by name, replacing existing ones", () => {
      const nsOld = makeNamespace({
        name: "my_s3",
        protocol: "s3",
        rootPath: "/old",
      });
      const nsOther = makeNamespace({ name: "my_gcs", protocol: "gcs" });
      actions.setNamespaces({ namespaces: [nsOld, nsOther] });

      const nsUpdated = makeNamespace({
        name: "my_s3",
        protocol: "s3",
        rootPath: "/new",
      });
      actions.setNamespaces({ namespaces: [nsUpdated] });

      expect(state.namespaces).toHaveLength(2);
      expect(state.namespaces).toEqual([nsUpdated, nsOther]);
    });

    it("should add new namespaces alongside existing ones", () => {
      const ns1 = makeNamespace({ name: "ns1" });
      actions.setNamespaces({ namespaces: [ns1] });

      const ns2 = makeNamespace({ name: "ns2" });
      actions.setNamespaces({ namespaces: [ns2] });

      expect(state.namespaces).toHaveLength(2);
      expect(state.namespaces).toEqual([ns1, ns2]);
    });

    it("should not affect entriesByPath", () => {
      const entry = makeEntry({ path: "file.txt" });
      actions.setEntries({
        namespace: "ns",
        prefix: null,
        entries: [entry],
      });

      actions.setNamespaces({
        namespaces: [makeNamespace({ name: "ns" })],
      });

      expect(state.entriesByPath.get("ns::")).toEqual([entry]);
    });
  });

  describe("setEntries", () => {
    it("should store entries keyed by namespace and prefix", () => {
      const entries = [
        makeEntry({ path: "a.txt", size: 100 }),
        makeEntry({ path: "b.txt", size: 200 }),
      ];

      actions.setEntries({
        namespace: "my_s3",
        prefix: "data/",
        entries,
      });

      expect(state.entriesByPath.get("my_s3::data/")).toEqual(entries);
    });

    it("should use empty string for null prefix", () => {
      const entries = [makeEntry({ path: "root.txt" })];

      actions.setEntries({
        namespace: "my_s3",
        prefix: null,
        entries,
      });

      expect(state.entriesByPath.get("my_s3::")).toEqual(entries);
    });

    it("should use empty string for undefined prefix", () => {
      const entries = [makeEntry({ path: "root.txt" })];

      actions.setEntries({
        namespace: "my_s3",
        prefix: undefined,
        entries,
      });

      expect(state.entriesByPath.get("my_s3::")).toEqual(entries);
    });

    it("should overwrite entries for the same namespace and prefix", () => {
      const oldEntries = [makeEntry({ path: "old.txt" })];
      const newEntries = [makeEntry({ path: "new.txt" })];

      actions.setEntries({
        namespace: "ns",
        prefix: "p/",
        entries: oldEntries,
      });
      actions.setEntries({
        namespace: "ns",
        prefix: "p/",
        entries: newEntries,
      });

      expect(state.entriesByPath.get("ns::p/")).toEqual(newEntries);
    });

    it("should store entries for different namespaces independently", () => {
      const entriesA = [makeEntry({ path: "a.txt" })];
      const entriesB = [makeEntry({ path: "b.txt" })];

      actions.setEntries({
        namespace: "ns_a",
        prefix: null,
        entries: entriesA,
      });
      actions.setEntries({
        namespace: "ns_b",
        prefix: null,
        entries: entriesB,
      });

      expect(state.entriesByPath.get("ns_a::")).toEqual(entriesA);
      expect(state.entriesByPath.get("ns_b::")).toEqual(entriesB);
    });

    it("should store entries for different prefixes independently", () => {
      const entriesRoot = [makeEntry({ path: "root.txt" })];
      const entriesSub = [makeEntry({ path: "sub/file.txt" })];

      actions.setEntries({
        namespace: "ns",
        prefix: null,
        entries: entriesRoot,
      });
      actions.setEntries({
        namespace: "ns",
        prefix: "sub/",
        entries: entriesSub,
      });

      expect(state.entriesByPath.get("ns::")).toEqual(entriesRoot);
      expect(state.entriesByPath.get("ns::sub/")).toEqual(entriesSub);
    });

    it("should not affect namespaces", () => {
      const ns = makeNamespace({ name: "ns" });
      actions.setNamespaces({ namespaces: [ns] });

      actions.setEntries({
        namespace: "ns",
        prefix: null,
        entries: [makeEntry({ path: "file.txt" })],
      });

      expect(state.namespaces).toEqual([ns]);
    });
  });

  describe("clearNamespaceCache", () => {
    it("should remove all entries for the given namespace", () => {
      actions.setEntries({
        namespace: "my_s3",
        prefix: null,
        entries: [makeEntry({ path: "root.txt" })],
      });
      actions.setEntries({
        namespace: "my_s3",
        prefix: "data/",
        entries: [makeEntry({ path: "data/file.csv" })],
      });
      actions.setEntries({
        namespace: "my_s3",
        prefix: "data/nested/",
        entries: [makeEntry({ path: "data/nested/deep.txt" })],
      });

      actions.clearNamespaceCache("my_s3");

      expect(state.entriesByPath.get("my_s3::")).toBeUndefined();
      expect(state.entriesByPath.get("my_s3::data/")).toBeUndefined();
      expect(state.entriesByPath.get("my_s3::data/nested/")).toBeUndefined();
    });

    it("should not affect entries from other namespaces", () => {
      const otherEntries = [makeEntry({ path: "other.txt" })];
      actions.setEntries({
        namespace: "my_s3",
        prefix: null,
        entries: [makeEntry({ path: "root.txt" })],
      });
      actions.setEntries({
        namespace: "my_gcs",
        prefix: null,
        entries: otherEntries,
      });

      actions.clearNamespaceCache("my_s3");

      expect(state.entriesByPath.get("my_s3::")).toBeUndefined();
      expect(state.entriesByPath.get("my_gcs::")).toEqual(otherEntries);
    });

    it("should not affect namespaces", () => {
      const ns = makeNamespace({ name: "my_s3" });
      actions.setNamespaces({ namespaces: [ns] });
      actions.setEntries({
        namespace: "my_s3",
        prefix: null,
        entries: [makeEntry({ path: "file.txt" })],
      });

      actions.clearNamespaceCache("my_s3");

      expect(state.namespaces).toEqual([ns]);
    });

    it("should be a no-op for a namespace with no cached entries", () => {
      actions.setEntries({
        namespace: "my_gcs",
        prefix: null,
        entries: [makeEntry({ path: "file.txt" })],
      });

      actions.clearNamespaceCache("nonexistent");

      expect(state.entriesByPath.get("my_gcs::")).toEqual([
        makeEntry({ path: "file.txt" }),
      ]);
    });
  });

  describe("filterFromVariables", () => {
    it("should keep namespaces whose variable is still in scope", () => {
      const ns1 = makeNamespace({ name: "var_a" });
      const ns2 = makeNamespace({ name: "var_b" });
      actions.setNamespaces({ namespaces: [ns1, ns2] });

      actions.filterFromVariables([
        "var_a" as VariableName,
        "var_b" as VariableName,
      ]);

      expect(state.namespaces).toEqual([ns1, ns2]);
    });

    it("should remove namespaces whose variable is no longer in scope", () => {
      const ns1 = makeNamespace({ name: "var_a" });
      const ns2 = makeNamespace({ name: "var_b" });
      actions.setNamespaces({ namespaces: [ns1, ns2] });

      actions.filterFromVariables(["var_a" as VariableName]);

      expect(state.namespaces).toEqual([ns1]);
    });

    it("should remove all named namespaces when given an empty variable list", () => {
      const ns1 = makeNamespace({ name: "var_a" });
      const ns2 = makeNamespace({ name: "var_b" });
      actions.setNamespaces({ namespaces: [ns1, ns2] });

      actions.filterFromVariables([]);

      expect(state.namespaces).toEqual([]);
    });

    it("should not affect entriesByPath", () => {
      const ns = makeNamespace({ name: "ns" });
      actions.setNamespaces({ namespaces: [ns] });

      const entry = makeEntry({ path: "file.txt" });
      actions.setEntries({
        namespace: "ns",
        prefix: null,
        entries: [entry],
      });

      actions.filterFromVariables([]);

      // Namespace removed, but entries remain (they are keyed independently)
      expect(state.namespaces).toEqual([]);
      expect(state.entriesByPath.get("ns::")).toEqual([entry]);
    });
  });
});
