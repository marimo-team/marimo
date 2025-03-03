/* Copyright 2024 Marimo. All rights reserved. */
import ReactDOM from "react-dom/client";
import { ThemeProvider } from "./theme/ThemeProvider";
import { ErrorBoundary } from "./components/editor/boundary/ErrorBoundary";
import { MarimoApp } from "./core/MarimoApp";
import { reportVitals } from "./utils/vitals";
import { Provider } from "jotai";
import { store } from "./core/state/jotai";
import { maybeRegisterVSCodeBindings } from "./core/vscode/vscode-bindings";
import { patchFetch, patchVegaLoader } from "./core/static/files";
import { isStaticNotebook } from "./core/static/static-state";
import { vegaLoader } from "./plugins/impl/vega/loader";
import { initializePlugins } from "./plugins/plugins";
import { cleanupAuthQueryParams } from "./core/network/auth";

maybeRegisterVSCodeBindings();
initializePlugins();
cleanupAuthQueryParams();

/**
 * Main entry point for the Marimo app.
 *
 * Sets up the Marimo app with a theme provider.
 */

// If we're in static mode, we need to patch fetch to use the virtual file
if (isStaticNotebook()) {
  patchFetch();
  patchVegaLoader(vegaLoader);
}

// Create root element for React rendering
const root = ReactDOM.createRoot(document.getElementById("root")!);

try {
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
} finally {
  reportVitals();
}
