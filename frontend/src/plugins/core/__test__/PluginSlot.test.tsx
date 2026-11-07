/* Copyright 2026 Marimo. All rights reserved. */

import { act, render } from "@testing-library/react";
import { createRef, StrictMode } from "react";
import { afterEach, describe, expect, test } from "vitest";
import { z } from "zod";
import {
  MarimoValueInputEvent,
  MarimoValueUpdateEvent,
} from "@/core/dom/events";
import type { IPlugin, IPluginProps, Setter } from "../../types";
import { PluginSlot, type PluginSlotHandle } from "../registerReactComponent";

type Value = number;

interface Mounted {
  host: HTMLElement;
  handle: React.RefObject<PluginSlotHandle | null>;
  events: unknown[];
  setValue: () => Setter<Value>;
  value: () => Value;
  unmount: () => void;
}

function mount(options: { strict?: boolean; initial?: Value } = {}): Mounted {
  const host = document.createElement("div");
  document.body.append(host);
  const events: unknown[] = [];
  host.addEventListener(MarimoValueInputEvent.TYPE, (e) => {
    events.push((e as CustomEvent<{ value: unknown }>).detail.value);
  });

  let latestProps: IPluginProps<Value, unknown> | undefined;
  const plugin: IPlugin<Value, unknown> = {
    tagName: "marimo-test-slot",
    validator: z.any(),
    render: (props) => {
      latestProps = props;
      return <span data-testid="value">{props.value}</span>;
    },
  };

  const handle = createRef<PluginSlotHandle>();
  const tree = (
    <PluginSlot
      hostElement={host}
      plugin={plugin}
      ref={handle}
      getInitialValue={() => options.initial ?? 0}
    />
  );
  const result = render(
    options.strict ? <StrictMode>{tree}</StrictMode> : tree,
  );

  return {
    host,
    handle,
    events,
    setValue: () => {
      if (!latestProps) {
        throw new Error("plugin did not render");
      }
      return latestProps.setValue;
    },
    value: () => {
      if (!latestProps) {
        throw new Error("plugin did not render");
      }
      return latestProps.value;
    },
    unmount: result.unmount,
  };
}

function pushHostValue(host: HTMLElement, value: Value) {
  host.dispatchEvent(
    MarimoValueUpdateEvent.create({ detail: { value, element: host } }),
  );
}

describe.each([
  { strict: false, label: "default" },
  { strict: true, label: "StrictMode" },
])("PluginSlot value dispatch ($label)", ({ strict }) => {
  afterEach(() => {
    document.body.innerHTML = "";
  });

  test("a plain value sends exactly one input event", () => {
    const m = mount({ strict });
    act(() => m.setValue()(5));
    expect(m.events).toEqual([5]);
    expect(m.value()).toBe(5);
  });

  test("an equal value sends no input event", () => {
    const m = mount({ strict, initial: 5 });
    act(() => m.setValue()(5));
    expect(m.events).toEqual([]);
  });

  test("functional updates chain within one tick and send one event each", () => {
    const m = mount({ strict });
    act(() => {
      m.setValue()((v) => v + 1);
      m.setValue()((v) => v + 1);
    });
    expect(m.events).toEqual([1, 2]);
    expect(m.value()).toBe(2);
  });

  test("a host update changes the value without an input event", () => {
    const m = mount({ strict });
    act(() => pushHostValue(m.host, 10));
    expect(m.value()).toBe(10);
    expect(m.events).toEqual([]);

    act(() => m.setValue()((v) => v + 1));
    expect(m.events).toEqual([11]);
  });

  test("reset restores the initial value without an input event", () => {
    const m = mount({ strict, initial: 3 });
    act(() => m.setValue()(7));
    expect(m.events).toEqual([7]);

    act(() => m.handle.current?.reset());
    expect(m.value()).toBe(3);
    expect(m.events).toEqual([7]);

    act(() => m.setValue()((v) => v + 1));
    expect(m.events).toEqual([7, 4]);
  });

  test("a host update to an equal value then a plugin change sends one event", () => {
    const m = mount({ strict, initial: 2 });
    act(() => pushHostValue(m.host, 2));
    act(() => m.setValue()(2));
    expect(m.events).toEqual([]);
  });
});

describe("PluginSlot value dispatch (shared behavior)", () => {
  afterEach(() => {
    document.body.innerHTML = "";
  });

  test("the input event bubbles to document and names the host element", () => {
    const m = mount();
    const seen: Array<{ value: unknown; element: HTMLElement }> = [];
    const listener = (e: Event) => {
      seen.push(
        (e as CustomEvent<{ value: unknown; element: HTMLElement }>).detail,
      );
    };
    document.addEventListener(MarimoValueInputEvent.TYPE, listener);
    act(() => m.setValue()(9));
    document.removeEventListener(MarimoValueInputEvent.TYPE, listener);
    expect(seen).toEqual([{ value: 9, element: m.host }]);
  });

  test("a shallow-equal object skips both the event and the re-render", () => {
    const host = document.createElement("div");
    document.body.append(host);
    const events: unknown[] = [];
    host.addEventListener(MarimoValueInputEvent.TYPE, (e) => {
      events.push((e as CustomEvent<{ value: unknown }>).detail.value);
    });
    let renders = 0;
    let setValue: Setter<{ a: number; b: string }> | undefined;
    const plugin: IPlugin<{ a: number; b: string }, unknown> = {
      tagName: "marimo-test-object",
      validator: z.any(),
      render: (props) => {
        renders++;
        setValue = props.setValue;
        return <span />;
      },
    };
    render(
      <PluginSlot
        hostElement={host}
        plugin={plugin}
        getInitialValue={() => ({ a: 1, b: "x" })}
      />,
    );
    const rendersAfterMount = renders;

    act(() => setValue?.((prev) => ({ ...prev, a: 1 })));
    expect(events).toEqual([]);
    expect(renders).toBe(rendersAfterMount);

    act(() => setValue?.((prev) => ({ ...prev, a: 2 })));
    expect(events).toEqual([{ a: 2, b: "x" }]);
    expect(renders).toBe(rendersAfterMount + 1);
  });
});
