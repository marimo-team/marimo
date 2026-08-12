/* Copyright 2026 Marimo. All rights reserved. */

import { cleanup, render } from "@testing-library/react";
import { createStore, Provider } from "jotai";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { userConfigAtom } from "@/core/config/config";
import {
  defaultUserConfig,
  parseUserConfig,
} from "@/core/config/config-schema";
import { FALLBACK_LOCALE } from "../locale";
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

function renderWithLocale(configLocale: string | null | undefined) {
  const store = createStore();
  store.set(
    userConfigAtom,
    parseUserConfig({ display: { locale: configLocale } }),
  );
  return render(
    <Provider store={store}>
      <LocaleProvider>
        <div>Test content</div>
      </LocaleProvider>
    </Provider>,
  );
}

describe("LocaleProvider", () => {
  beforeEach(() => {
    vi.stubGlobal("navigator", { language: undefined as string | undefined });
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    vi.clearAllMocks();
  });

  it("passes a valid configured locale through unchanged", () => {
    const { getByTestId } = renderWithLocale("es-ES");
    expect(getByTestId("i18n-provider").dataset.locale).toBe("es-ES");
  });

  it("prefers the browser locale when config is unset", () => {
    vi.stubGlobal("navigator", { language: "de-DE" });
    const { getByTestId } = renderWithLocale(null);
    expect(getByTestId("i18n-provider").dataset.locale).toBe("de-DE");
  });

  it.each([null, undefined])(
    "falls back to %s config + unusable browser locale",
    (configLocale) => {
      const { getByTestId } = renderWithLocale(configLocale);
      expect(getByTestId("i18n-provider").dataset.locale).toBe(FALLBACK_LOCALE);
    },
  );

  it("sanitizes a POSIX-tagged browser locale (issue #9938)", () => {
    vi.stubGlobal("navigator", { language: "en-US@posix" });
    const { getByTestId } = renderWithLocale(null);
    expect(getByTestId("i18n-provider").dataset.locale).toBe("en-US");
  });

  it("falls back to the browser locale when the configured locale is unusable", () => {
    vi.stubGlobal("navigator", { language: "de-DE" });
    const { getByTestId } = renderWithLocale("@@@");
    expect(getByTestId("i18n-provider").dataset.locale).toBe("de-DE");
  });

  it("resolves a concrete locale for the default config", () => {
    vi.stubGlobal("navigator", { language: "fr-FR" });
    const store = createStore();
    store.set(userConfigAtom, defaultUserConfig());
    const { getByTestId } = render(
      <Provider store={store}>
        <LocaleProvider>
          <div>Default config test</div>
        </LocaleProvider>
      </Provider>,
    );
    expect(getByTestId("i18n-provider").dataset.locale).toBe("fr-FR");
  });

  it("renders children", () => {
    const store = createStore();
    store.set(
      userConfigAtom,
      parseUserConfig({ display: { locale: "en-US" } }),
    );
    const { getByRole } = render(
      <Provider store={store}>
        <LocaleProvider>
          <button type="button">Test Button</button>
        </LocaleProvider>
      </Provider>,
    );
    expect(getByRole("button", { name: "Test Button" })).toBeInTheDocument();
  });
});
