/* Copyright 2024 Marimo. All rights reserved. */
import { createRoot } from "react-dom/client";
import { ThemeProvider } from "./theme/ThemeProvider";
import { ErrorBoundary } from "./components/editor/boundary/ErrorBoundary";
import { MarimoApp, preloadPage } from "./core/MarimoApp";
import { reportVitals } from "./utils/vitals";
import { Provider } from "jotai";
import { store } from "./core/state/jotai";
import { maybeRegisterVSCodeBindings } from "./core/vscode/vscode-bindings";
import { patchFetch, patchVegaLoader } from "./core/static/files";
import { isStaticNotebook } from "./core/static/static-state";
import { vegaLoader } from "./plugins/impl/vega/loader";
import { initializePlugins } from "./plugins/plugins";
import { cleanupAuthQueryParams } from "./core/network/auth";
import {
  parseAppConfig,
  parseConfigOverrides,
  parseUserConfig,
} from "./core/config/config-schema";
import { type AppMode, initialModeAtom, viewStateAtom } from "./core/mode";
import { codeAtom, filenameAtom } from "./core/saving/file-state";
import { Logger } from "@/utils/Logger";
import { z } from "zod";
import { getFilenameFromDOM } from "@/core/dom/htmlUtils";
import {
  showCodeInRunModeAtom,
  marimoVersionAtom,
  serverTokenAtom,
} from "@/core/meta/state";
import { appConfigAtom, userConfigAtom } from "@/core/config/config";
import { configOverridesAtom } from "@/core/config/config";
import { getMarimoCode } from "@/core/meta/globals";

let hasMounted = false;

/**
 * Main entry point for the mairmo app.
 *
 * Sets up the mairmo app with a theme provider.
 */
export function mount(options: unknown, el: Element): Error | undefined {
  if (hasMounted) {
    Logger.warn("marimo app has already been mounted.");
    return new Error("marimo app has already been mounted.");
  }

  hasMounted = true;

  const root = createRoot(el);

  try {
    // Init side-effects
    maybeRegisterVSCodeBindings();
    initializePlugins();
    cleanupAuthQueryParams();

    // Patches
    if (isStaticNotebook()) {
      // If we're in static mode, we need to patch fetch to use the virtual file
      patchFetch();
      patchVegaLoader(vegaLoader);
    }

    // Init store
    initStore(options);

    root.render(
      <Provider store={store}>
        <ThemeProvider>
          <MarimoApp />
        </ThemeProvider>
      </Provider>,
    );
  } catch (error) {
    // Most likely, configuration failed to parse.
    const Throw = () => {
      throw error;
    };
    root.render(
      <ErrorBoundary>
        <Throw />
      </ErrorBoundary>,
    );
    return error as Error;
  } finally {
    reportVitals();
  }
}

const passthroughObject = z
  .object({})
  .passthrough() // Allow any extra fields
  .nullish()
  .default({}) // Default to empty object
  .transform((val) => {
    if (val) {
      return val;
    }
    if (typeof val === "string") {
      Logger.warn(
        "[marimo] received JSON string instead of object. Parsing...",
      );
      return JSON.parse(val);
    }
    Logger.warn("[marimo] missing config data");
    return {};
  });

// This should be extremely backwards compatible and require no options
const mountOptionsSchema = z.object({
  /**
   * filename of the notebook to open
   */
  filename: z
    .string()
    .nullish()
    .transform((val) => {
      if (val) {
        return val;
      }
      Logger.warn("No filename provided, using fallback");
      return getFilenameFromDOM();
    }),
  /**
   * notebook code
   */
  code: z
    .string()
    .nullish()
    .transform((val) => val ?? getMarimoCode() ?? ""),
  /**
   * marimo version
   */
  version: z
    .string()
    .nullish()
    .transform((val) => val ?? "unknown"),
  /**
   * 'edit' or 'read'/'run' or 'home'
   */
  mode: z.enum(["edit", "read", "home", "run"]).transform((val): AppMode => {
    if (val === "run") {
      return "read";
    }
    return val;
  }),
  /**
   * marimo config
   */
  config: passthroughObject,
  /**
   * marimo config overrides
   */
  configOverrides: passthroughObject,
  /**
   * marimo app config
   */
  appConfig: passthroughObject,
  /**
   * show code in run mode
   */
  view: z
    .object({
      showAppCode: z.boolean().default(true),
    })
    .nullish()
    .transform((val) => val ?? { showAppCode: true }),

  /**
   * server token
   */
  serverToken: z
    .string()
    .nullish()
    .transform((val) => val ?? ""),
});

function initStore(options: unknown) {
  const parsedOptions = mountOptionsSchema.safeParse(options);
  if (!parsedOptions.success) {
    Logger.error("Invalid marimo mount options", parsedOptions.error);
    throw new Error("Invalid marimo mount options");
  }
  const mode = parsedOptions.data.mode as AppMode;
  preloadPage(mode);

  // Files
  store.set(filenameAtom, parsedOptions.data.filename);
  store.set(codeAtom, parsedOptions.data.code);
  store.set(initialModeAtom, mode);

  // Meta
  store.set(marimoVersionAtom, parsedOptions.data.version);
  store.set(showCodeInRunModeAtom, parsedOptions.data.view.showAppCode);
  store.set(viewStateAtom, { mode, cellAnchor: null });
  store.set(serverTokenAtom, parsedOptions.data.serverToken);

  // Config
  store.set(
    configOverridesAtom,
    parseConfigOverrides(parsedOptions.data.configOverrides),
  );
  store.set(userConfigAtom, parseUserConfig(parsedOptions.data.config));
  store.set(appConfigAtom, parseAppConfig(parsedOptions.data.appConfig));
}

export const visibleForTesting = {
  reset: () => {
    hasMounted = false;
  },
};
