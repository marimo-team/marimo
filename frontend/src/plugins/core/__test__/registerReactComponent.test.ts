/* Copyright 2026 Marimo. All rights reserved. */

import ReactDOM from "react-dom/client";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { z } from "zod";
import {
  isCustomMarimoElement,
  registerReactComponent,
} from "../registerReactComponent";

// Each custom element name can only be registered once per jsdom window,
// so we use a counter to generate unique tag names across tests.
let tagCounter = 0;
function uniqueTag(base: string) {
  return `marimo-test-${base}-${++tagCounter}`;
}

function makePlugin(tagName: string) {
  return {
    tagName,
    validator: z.any(),
    render: () => null as never,
  };
}

describe("isCustomMarimoElement", () => {
  test("returns false for null", () => {
    expect(isCustomMarimoElement(null)).toBe(false);
  });

  test("returns false for a regular HTMLElement", () => {
    const div = document.createElement("div");
    expect(isCustomMarimoElement(div)).toBe(false);
  });

  test("returns false for a non-HTMLElement", () => {
    const svg = document.createElementNS(
      "http://www.w3.org/2000/svg",
      "circle",
    );
    expect(isCustomMarimoElement(svg as Element)).toBe(false);
  });

  test("returns true for a registered marimo custom element", () => {
    const tag = uniqueTag("is-custom");
    registerReactComponent(makePlugin(tag));
    const el = document.createElement(tag);
    expect(isCustomMarimoElement(el)).toBe(true);
  });

  test("returns false for an element with wrong __type__ value", () => {
    const div = document.createElement("div") as unknown as HTMLElement & {
      __type__: string;
    };
    div.__type__ = "something_else";
    expect(isCustomMarimoElement(div)).toBe(false);
  });
});

describe("connectedCallback - light DOM nesting detection", () => {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  let createRootSpy: any;
  const mockRoot = {
    render: vi.fn(),
    unmount: vi.fn(),
  };

  beforeEach(() => {
    createRootSpy = vi
      .spyOn(ReactDOM, "createRoot")
      .mockReturnValue(mockRoot as unknown as ReactDOM.Root);
  });

  afterEach(() => {
    createRootSpy.mockRestore();
    mockRoot.render.mockClear();
    mockRoot.unmount.mockClear();
  });

  test("skips mounting when element is a light DOM child of another marimo element", () => {
    const parentTag = uniqueTag("parent");
    const childTag = uniqueTag("child");
    registerReactComponent(makePlugin(parentTag));
    registerReactComponent(makePlugin(childTag));

    const parent = document.createElement(parentTag);
    const child = document.createElement(childTag);
    parent.append(child);

    createRootSpy.mockClear();
    document.body.append(parent);

    // Only the parent should mount; the child is skipped because it
    // detects a marimo ancestor in the light DOM.
    expect(createRootSpy).toHaveBeenCalledTimes(1);
    expect(createRootSpy).toHaveBeenCalledWith(parent.shadowRoot);

    parent.remove();
  });

  test("mounts when element is not nested inside a marimo element", () => {
    const tag = uniqueTag("standalone");
    registerReactComponent(makePlugin(tag));

    const el = document.createElement(tag);
    createRootSpy.mockClear();

    document.body.append(el);

    expect(createRootSpy).toHaveBeenCalledTimes(1);
    expect(createRootSpy).toHaveBeenCalledWith(el.shadowRoot);

    el.remove();
  });

  test("mounts when nested inside a regular (non-marimo) element", () => {
    const tag = uniqueTag("in-div");
    registerReactComponent(makePlugin(tag));

    const wrapper = document.createElement("div");
    const el = document.createElement(tag);
    wrapper.append(el);

    createRootSpy.mockClear();
    document.body.append(wrapper);

    expect(createRootSpy).toHaveBeenCalledTimes(1);
    expect(createRootSpy).toHaveBeenCalledWith(el.shadowRoot);

    wrapper.remove();
  });

  test("skips mounting for deeply nested marimo element through non-marimo wrappers", () => {
    const outerTag = uniqueTag("outer");
    const innerTag = uniqueTag("inner");
    registerReactComponent(makePlugin(outerTag));
    registerReactComponent(makePlugin(innerTag));

    const outer = document.createElement(outerTag);
    const div = document.createElement("div");
    const inner = document.createElement(innerTag);

    // Structure: outer > div > inner
    outer.append(div);
    div.append(inner);

    createRootSpy.mockClear();
    document.body.append(outer);

    // Only outer mounts; inner is skipped because a marimo ancestor
    // is found when traversing through the intermediate div.
    expect(createRootSpy).toHaveBeenCalledTimes(1);
    expect(createRootSpy).toHaveBeenCalledWith(outer.shadowRoot);

    outer.remove();
  });

  test("mounts both sibling marimo elements (neither is a child of the other)", () => {
    const tagA = uniqueTag("sibling-a");
    const tagB = uniqueTag("sibling-b");
    registerReactComponent(makePlugin(tagA));
    registerReactComponent(makePlugin(tagB));

    const wrapper = document.createElement("div");
    const a = document.createElement(tagA);
    const b = document.createElement(tagB);
    wrapper.append(a);
    wrapper.append(b);

    createRootSpy.mockClear();
    document.body.append(wrapper);

    // Both siblings should mount since neither is a child of the other.
    expect(createRootSpy).toHaveBeenCalledTimes(2);

    wrapper.remove();
  });

  test("mounts when element is inside the shadow DOM of another marimo element", () => {
    const outerTag = uniqueTag("shadow-outer");
    const innerTag = uniqueTag("shadow-inner");
    registerReactComponent(makePlugin(outerTag));
    registerReactComponent(makePlugin(innerTag));

    const outer = document.createElement(outerTag);
    const inner = document.createElement(innerTag);

    // Place the inner element inside the outer element's shadow root,
    // simulating how getChildren() -> renderHTML() re-creates children
    // in the shadow DOM. parentElement traversal stays within the
    // shadow root boundary, so inner should NOT detect outer as an
    // ancestor and should mount normally.
    outer.shadowRoot?.append(inner);

    createRootSpy.mockClear();
    document.body.append(outer);

    // Both elements should mount: outer in the document, inner in the
    // shadow root (parentElement traversal doesn't cross shadow boundary).
    expect(createRootSpy).toHaveBeenCalledTimes(2);

    outer.remove();
  });
});
