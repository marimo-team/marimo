/* Copyright 2026 Marimo. All rights reserved. */

import { cleanup, render } from "@testing-library/react";
import { createStore, Provider } from "jotai";
import { afterEach, describe, expect, it, vi } from "vitest";
import { userConfigAtom } from "@/core/config/config";
import {
  defaultUserConfig,
  parseUserConfig,
} from "@/core/config/config-schema";
import { LocaleProvider } from "../locale-provider";

vi.mock("react-aria-components", () => ({
  I18nProvider: ({
    children,
    locale,
  }: {
    children: React.ReactNode;
    locale?: string;
  }) => (
    <div data-testid="i18n-provider" data-locale={locale ?? ""}>
      {children}
    </div>
  ),
}));

describe("LocaleProvider", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("omits locale when config locale is null", () => {
    const store = createStore();
    const config = parseUserConfig({ display: { locale: null } });
    store.set(userConfigAtom, config);

    const { getByTestId } = render(
      <Provider store={store}>
        <LocaleProvider>
          <div>Test content</div>
        </LocaleProvider>
      </Provider>,
    );

    expect(getByTestId("i18n-provider").dataset.locale).toBe("");
  });

  it("omits locale when config locale is undefined", () => {
    const store = createStore();
    const config = parseUserConfig({ display: { locale: undefined } });
    store.set(userConfigAtom, config);

    const { getByTestId } = render(
      <Provider store={store}>
        <LocaleProvider>
          <div>Test content</div>
        </LocaleProvider>
      </Provider>,
    );

    expect(getByTestId("i18n-provider").dataset.locale).toBe("");
  });

  it("passes locale when config locale is valid", () => {
    const store = createStore();
    const config = parseUserConfig({ display: { locale: "es-ES" } });
    store.set(userConfigAtom, config);

    const { getByTestId } = render(
      <Provider store={store}>
        <LocaleProvider>
          <div>Test content</div>
        </LocaleProvider>
      </Provider>,
    );

    expect(getByTestId("i18n-provider").dataset.locale).toBe("es-ES");
  });

  it("omits locale when config locale is invalid", () => {
    const store = createStore();
    const config = parseUserConfig({ display: { locale: "en-US@posix" } });
    store.set(userConfigAtom, config);

    const { getByTestId } = render(
      <Provider store={store}>
        <LocaleProvider>
          <div>Test content</div>
        </LocaleProvider>
      </Provider>,
    );

    expect(getByTestId("i18n-provider").dataset.locale).toBe("");
  });

  it("passes different valid locale values", () => {
    for (const locale of ["en-US", "fr-FR", "de-DE", "ja-JP"]) {
      const store = createStore();
      const config = parseUserConfig({ display: { locale } });
      store.set(userConfigAtom, config);

      const { getByTestId } = render(
        <Provider store={store}>
          <LocaleProvider>
            <div>Test content for {locale}</div>
          </LocaleProvider>
        </Provider>,
      );

      expect(getByTestId("i18n-provider").dataset.locale).toBe(locale);
      cleanup();
    }
  });

  it("renders children correctly", () => {
    const store = createStore();
    const config = parseUserConfig({ display: { locale: "en-US" } });
    store.set(userConfigAtom, config);

    const { getByText, getByRole } = render(
      <Provider store={store}>
        <LocaleProvider>
          <div>
            <h1>Test Heading</h1>
            <p>Test paragraph</p>
            <button type="button">Test Button</button>
          </div>
        </LocaleProvider>
      </Provider>,
    );

    expect(getByText("Test Heading")).toBeInTheDocument();
    expect(getByText("Test paragraph")).toBeInTheDocument();
    expect(getByRole("button", { name: "Test Button" })).toBeInTheDocument();
  });

  it("omits locale for default config", () => {
    const store = createStore();
    store.set(userConfigAtom, defaultUserConfig());

    const { getByTestId } = render(
      <Provider store={store}>
        <LocaleProvider>
          <div>Test content</div>
        </LocaleProvider>
      </Provider>,
    );

    expect(getByTestId("i18n-provider").dataset.locale).toBe("");
  });
});
