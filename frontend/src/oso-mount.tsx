/* Copyright 2024 Marimo. All rights reserved. */

import type * as api from "@marimo-team/marimo-api";
import { Provider } from "jotai";
import { createRoot } from "react-dom/client";
import { z } from "zod";
import {
  appConfigAtom,
  configOverridesAtom,
  userConfigAtom,
} from "@/core/config/config";
//import { KnownQueryParams } from "@/core/constants";
import { getFilenameFromDOM } from "@/core/dom/htmlUtils";
import { getMarimoCode } from "@/core/meta/globals";
import {
  marimoVersionAtom,
  serverTokenAtom,
  showCodeInRunModeAtom,
} from "@/core/meta/state";
import { Logger } from "@/utils/Logger";
import { ErrorBoundary } from "./components/editor/boundary/ErrorBoundary";
import { notebookAtom } from "./core/cells/cells";
import { notebookStateFromSession } from "./core/cells/session";
import {
  parseAppConfig,
  parseConfigOverrides,
  parseUserConfig,
} from "./core/config/config-schema";
import { type AppMode, initialModeAtom, viewStateAtom } from "./core/mode";
import { cleanupAuthQueryParams } from "./core/network/auth";
import { requestClientAtom } from "./core/network/requests";
import { resolveRequestClient } from "./core/network/resolve";
import {
  DEFAULT_RUNTIME_CONFIG,
  runtimeConfigAtom,
} from "./core/runtime/config";
import { codeAtom, filenameAtom } from "./core/saving/file-state";
import { store } from "./core/state/jotai";
import { patchFetch, patchVegaLoader } from "./core/static/files";
import { isStaticNotebook } from "./core/static/static-state";
import { maybeRegisterVSCodeBindings } from "./core/vscode/vscode-bindings";
import type { FileStore } from "./core/wasm/store";
import { notebookFileStore } from "./core/wasm/store";
import { vegaLoader } from "./plugins/impl/vega/loader";
import { initializePlugins } from "./plugins/plugins";
import { ThemeProvider } from "./theme/ThemeProvider";
import { reportVitals } from "./utils/vitals";
import { OSOWrapper } from "./oso-extensions/wrapper";
import { OSONotebook, LazyOSONotebookPage } from "./oso-extensions/OSONotebook";
import { FragmentStore } from "./oso-extensions/fragment-store";


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

  const fragmentStore = FragmentStore.load();
  if (window.__DEBUG__) {
    window.__fragmentStore = fragmentStore;
  }


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
    initStore(fragmentStore, options);

    root.render(
      <Provider store={store}>
        <ThemeProvider>
          <OSOWrapper fragmentStore={fragmentStore}>
            <OSONotebook />
          </OSOWrapper>
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

  /**
   * File stores for persistence
   */
  fileStores: z.array(z.custom<FileStore>()).optional(),

  /**
   * Serialized Session["NotebookSessionV1"] snapshot
   */
  session: z.union([
    z.null().optional(),
    z
      .object({
        // Rough shape, we don't need to validate the full schema
        version: z.literal("1"),
        metadata: z.any(),
        cells: z.array(z.any()),
      })
      .passthrough()
      .transform((val) => val as api.Session["NotebookSessionV1"]),
  ]),

  /**
   * Serialized Notebook["NotebookV1"] snapshot
   */
  notebook: z.union([
    z.null().optional(),
    z
      .object({
        // Rough shape, we don't need to validate the full schema
        version: z.literal("1"),
        metadata: z.any(),
        cells: z.array(z.any()),
      })
      .passthrough()
      .transform((val) => val as api.Notebook["NotebookV1"]),
  ]),

  /**
   * Runtime configs
   */
  runtimeConfig: z
    .array(
      z
        .object({
          url: z.string(),
          authToken: z.string().nullish(),
        })
        .passthrough(),
    )
    .nullish()
    .transform((val) => val ?? []),
});

class OSOFileStore implements FileStore {
  private fragmentStore: FragmentStore;
  constructor(fragmentStore: FragmentStore) {
    this.fragmentStore = fragmentStore;
  }

  saveFile(contents: string): void {
    this.fragmentStore.setString("code", contents);
    this.fragmentStore.commit();
  }

  readFile(): string | null | Promise<string | null> {
    return this.fragmentStore.getString("code");
  }
}

function initStore(fragmentStore: FragmentStore, options: unknown) {
  const parsedOptions = mountOptionsSchema.safeParse(options);
  if (!parsedOptions.success) {
    Logger.error("Invalid marimo mount options", parsedOptions.error);
    throw new Error("Invalid marimo mount options");
  }
  const mode = "edit";
  LazyOSONotebookPage.preload();

  // Initialize file stores if provided
  if (
    parsedOptions.data.fileStores &&
    parsedOptions.data.fileStores.length > 0
  ) {
    Logger.log("🗄️ Initializing file stores via mount...");
    // Override all filestores by popping all values in notebookFileStore
    notebookFileStore.overrideStores([
      new OSOFileStore(fragmentStore),
    ]);
    Logger.log(
      `🗄️ Overrode filestores with ${parsedOptions.data.fileStores.length} file store(s) into notebookFileStore`,
    );
  }

  // Configure networking layer
  store.set(requestClientAtom, resolveRequestClient());

  // Files
  store.set(filenameAtom, parsedOptions.data.filename);
  store.set(codeAtom, parsedOptions.data.code);
  store.set(initialModeAtom, mode);

  // Meta
  store.set(marimoVersionAtom, parsedOptions.data.version);
  store.set(showCodeInRunModeAtom, parsedOptions.data.view.showAppCode);

  // Check for view-as parameter to start in present mode
  const initialViewMode = "edit";
  store.set(viewStateAtom, { mode: initialViewMode, cellAnchor: null });
  store.set(serverTokenAtom, parsedOptions.data.serverToken);

  // Config
  store.set(
    configOverridesAtom,
    parseConfigOverrides(parsedOptions.data.configOverrides),
  );
  store.set(userConfigAtom, parseUserConfig(parsedOptions.data.config));
  store.set(appConfigAtom, parseAppConfig(parsedOptions.data.appConfig));

  // Runtime config
  if (parsedOptions.data.runtimeConfig.length > 0) {
    const firstRuntimeConfig = parsedOptions.data.runtimeConfig[0];
    Logger.debug("⚡ Runtime URL", firstRuntimeConfig.url);
    store.set(runtimeConfigAtom, {
      ...firstRuntimeConfig,
      serverToken: parsedOptions.data.serverToken,
    });
  } else {
    store.set(runtimeConfigAtom, {
      ...DEFAULT_RUNTIME_CONFIG,
      serverToken: parsedOptions.data.serverToken,
    });
  }

  // Session/notebook
  const notebook = notebookStateFromSession(
    parsedOptions.data.session,
    parsedOptions.data.notebook,
  );
  if (notebook) {
    store.set(notebookAtom, notebook);
  }
}

export const visibleForTesting = {
  reset: () => {
    hasMounted = false;
  },
};
