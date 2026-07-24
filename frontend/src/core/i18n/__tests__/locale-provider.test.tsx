/* Copyright 2026 Marimo. All rights reserved. */

import { cleanup, render } from "@testing-library/react";
import { createStore, Provider } from "jotai";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { userConfigAtom } from "@/core/config/config";
import {
  defaultUserConfig,
  parseUserConfig,
} from "@/core/config/config-schema";
import { FALLBACK_LOCALE, normalizeBrowserLocale, safeLocale } from "../locale";
import { LocaleProvider } from "../locale-provider";

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

describe("normalizeBrowserLocale", () => {
  it("strips @posix-style modifiers used by Playwright Chromium", () => {
    expect(normalizeBrowserLocale("en-US@posix")).toBe("en-US");
  });

  it("maps underscore locales and drops charset suffixes", () => {
    expect(normalizeBrowserLocale("en_US.UTF-8")).toBe("en-US");
  });

  it("returns fallback for empty or garbage tags", () => {
    expect(normalizeBrowserLocale(undefined)).toBe(FALLBACK_LOCALE);
    expect(normalizeBrowserLocale("")).toBe(FALLBACK_LOCALE);
    expect(normalizeBrowserLocale("@@@")).toBe(FALLBACK_LOCALE);
  });

  it("keeps valid BCP47 tags", () => {
    expect(normalizeBrowserLocale("de-DE")).toBe("de-DE");
  });

  it("preserves base language for de-DE@posix", () => {
    expect(normalizeBrowserLocale("de-DE@posix")).toBe("de-DE");
  });
});

describe("safeLocale", () => {
  beforeEach(() => {
    vi.stubGlobal("navigator", {
      language: undefined as string | undefined,
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("prefers a valid configured locale", () => {
    expect(safeLocale("fr-FR")).toBe("fr-FR");
  });

  it("canonicalizes underscore configured locales for I18nProvider", () => {
    expect(safeLocale("en_US")).toBe("en-US");
  });

  it("normalizes configured locales with @posix before falling back", () => {
    expect(safeLocale("en-US@posix")).toBe("en-US");
  });

  it("normalizes configured locales with charset suffixes", () => {
    expect(safeLocale("en_US.UTF-8")).toBe("en-US");
  });

  it("falls back through browser language when config is invalid", () => {
    vi.stubGlobal("navigator", { language: "en-US@posix" });
    expect(safeLocale("not-a-real-locale-zzzz")).toBe("en-US");
  });
});

describe("LocaleProvider", () => {
  beforeEach(() => {
    vi.stubGlobal("navigator", {
      language: undefined as string | undefined,
    });
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    vi.clearAllMocks();
  });

  it("uses fallback locale when config locale is null", () => {
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
    // null config → normalize browser language (unset → FALLBACK_LOCALE)
    expect(i18nProvider.dataset.locale).toBe(FALLBACK_LOCALE);
    expect(i18nProvider).toHaveTextContent("Test content");
  });

  it("uses fallback locale when config locale is undefined", () => {
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
    expect(i18nProvider.dataset.locale).toBe(FALLBACK_LOCALE);
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

  it("should use default config when no config is provided", () => {
    const store = createStore();
    store.set(userConfigAtom, defaultUserConfig());

    const { getByTestId } = render(
      <Provider store={store}>
        <LocaleProvider>
          <div>Default config test</div>
        </LocaleProvider>
      </Provider>,
    );

    const i18nProvider = getByTestId("i18n-provider");
    expect(i18nProvider).toBeInTheDocument();
    expect(i18nProvider).toHaveTextContent("Default config test");
  });

  it("sanitizes browser locale when config is unset and navigator is posix-tagged", () => {
    vi.stubGlobal("navigator", { language: "en-US@posix" });
    const store = createStore();
    const config = parseUserConfig({ display: { locale: null } });
    store.set(userConfigAtom, config);

    const { getByTestId } = render(
      <Provider store={store}>
        <LocaleProvider>
          <div>posix</div>
        </LocaleProvider>
      </Provider>,
    );

    expect(getByTestId("i18n-provider").dataset.locale).toBe("en-US");
  });
});
