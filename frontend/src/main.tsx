/* Copyright 2023 Marimo. All rights reserved. */
import React from "react";
import ReactDOM from "react-dom/client";
import { worker } from "./mocks/browser";
import { ThemeProvider } from "./theme/ThemeProvider";
import { ErrorBoundary } from "./components/editor/boundary/ErrorBoundary";
import { MarimoApp } from "./core/MarimoApp";
import { Logger } from "./utils/Logger";
import { reportVitals } from "./utils/vitals";
import { Provider } from "jotai";
import { store } from "./core/state/jotai";
import { maybeRegisterVSCodeBindings } from "./core/vscode/vscode-bindings";

maybeRegisterVSCodeBindings();

/**
 * Main entry point for the Marimo app.
 *
 * Sets up the Marimo app with a theme provider.
 * This file will optionally start the MSW worker if enabled.
 */

if (import.meta.env.DEV && import.meta.env.VITE_MSW) {
  worker.start({
    onUnhandledRequest(req) {
      if (req.url.href.startsWith("/kernel")) {
        Logger.error(
          `Found an unhandled ${req.method} request to ${req.url.href}`
        );
      }
    },
  });
}

// eslint-disable-next-line @typescript-eslint/no-non-null-assertion, ssr-friendly/no-dom-globals-in-module-scope
const root = ReactDOM.createRoot(document.getElementById("root")!);

try {
  root.render(
    <React.StrictMode>
      <Provider store={store}>
        <ThemeProvider>
          <MarimoApp />
        </ThemeProvider>
      </Provider>
    </React.StrictMode>
  );
} catch (error) {
  // Most likely, configuration failed to parse.
  const Throw = () => {
    throw error;
  };
  root.render(
    <ErrorBoundary>
      <Throw />
    </ErrorBoundary>
  );
} finally {
  reportVitals();
}
