/* Copyright 2026 Marimo. All rights reserved. */

import { cleanup, render } from "@testing-library/react";
import { createStore, Provider } from "jotai";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { userConfigAtom } from "@/core/config/config";
import {
  defaultUserConfig,
  parseUserConfig,
} from "@/core/config/config-schema";
import { LocaleProvider } from "../locale-provider";

// Mock navigator.language with a getter
let mockNavigatorLanguage: string | undefined;

Object.defineProperty(window, "navigator", {
  value: {
    get language() {
      return mockNavigatorLanguage;
    },
  },
  writable: true,
});

// Mock react-aria-components I18nProvider
vi.mock("react-aria-components", () => ({
  I18nProvider: ({
    children,
    locale,
  }: {
    children: React.ReactNode;
    locale: string;
  }) => (
    <div data-testid="i18n-provider" data-locale={locale}>
      {children}
    </div>
  ),
}));

describe("LocaleProvider", () => {
  beforeEach(() => {
    // Reset the mock before each test
    mockNavigatorLanguage = undefined;
  });

  afterEach(() => {
    cleanup();
    // Clear all mocks after each test
    mockNavigatorLanguage = undefined;
    vi.clearAllMocks();
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
    expect(i18nProvider.dataset.locale).toBe(undefined);
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
    expect(i18nProvider.dataset.locale).toBe(undefined);
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
    expect(i18nProvider.dataset.locale).toBe(testLocale);
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
      expect(i18nProvider.dataset.locale).toBe(locale);
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
    mockNavigatorLanguage = "de-DE";

    const store = createStore();
    const config = defaultUserConfig();
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
    // When no locale is specified in config, it should use navigator.language
    expect(i18nProvider.dataset.locale).toBe("de-DE");
    expect(i18nProvider).toHaveTextContent("Test content");
  });
});
