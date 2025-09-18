/* Copyright 2024 Marimo. All rights reserved. */

import { cleanup, render } from "@testing-library/react";
import { createStore, Provider } from "jotai";
import { afterEach, describe, expect, it, vi } from "vitest";
import { userConfigAtom } from "@/core/config/config";
import { parseUserConfig } from "@/core/config/config-schema";
import { LocaleProvider } from "../local-provider";

// Mock react-aria-components I18nProvider
vi.mock("react-aria-components", () => ({
  I18nProvider: ({
    children,
    locale,
  }: {
    children: React.ReactNode;
    locale?: string;
  }) => (
    <div data-testid="i18n-provider" data-locale={locale}>
      {children}
    </div>
  ),
}));

describe("LocaleProvider", () => {
  afterEach(() => {
    cleanup();
  });

  it("should render I18nProvider without locale when locale is null", () => {
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

    const i18nProvider = getByTestId("i18n-provider");
    expect(i18nProvider).toBeInTheDocument();
    expect(i18nProvider.getAttribute("data-locale")).toBe(null);
    expect(i18nProvider).toHaveTextContent("Test content");
  });

  it("should render I18nProvider without locale when locale is undefined", () => {
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

    const i18nProvider = getByTestId("i18n-provider");
    expect(i18nProvider).toBeInTheDocument();
    expect(i18nProvider.getAttribute("data-locale")).toBe(null);
    expect(i18nProvider).toHaveTextContent("Test content");
  });

  it("should render I18nProvider with locale when locale is provided", () => {
    const store = createStore();
    const testLocale = "es-ES";
    const config = parseUserConfig({ display: { locale: testLocale } });
    store.set(userConfigAtom, config);

    const { getByTestId } = render(
      <Provider store={store}>
        <LocaleProvider>
          <div>Test content</div>
        </LocaleProvider>
      </Provider>,
    );

    const i18nProvider = getByTestId("i18n-provider");
    expect(i18nProvider).toBeInTheDocument();
    expect(i18nProvider.getAttribute("data-locale")).toBe(testLocale);
    expect(i18nProvider).toHaveTextContent("Test content");
  });

  it("should render I18nProvider with different locale values", () => {
    const testCases = ["en-US", "fr-FR", "de-DE", "ja-JP"];

    testCases.forEach((locale) => {
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

      const i18nProvider = getByTestId("i18n-provider");
      expect(i18nProvider.getAttribute("data-locale")).toBe(locale);
      expect(i18nProvider).toHaveTextContent(`Test content for ${locale}`);

      // Clean up after each iteration
      cleanup();
    });
  });

  it("should render children correctly", () => {
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

  it("should auto-detect locale when no locale is set in config", () => {
    const store = createStore();
    const config = parseUserConfig({});
    store.set(userConfigAtom, config);

    const { getByTestId } = render(
      <Provider store={store}>
        <LocaleProvider>
          <div>Test content</div>
        </LocaleProvider>
      </Provider>,
    );

    const i18nProvider = getByTestId("i18n-provider");
    expect(i18nProvider).toBeInTheDocument();
    // When no locale is specified in config, it should default to undefined/null
    expect(i18nProvider.getAttribute("data-locale")).toBe(null);
    expect(i18nProvider).toHaveTextContent("Test content");
  });
});
