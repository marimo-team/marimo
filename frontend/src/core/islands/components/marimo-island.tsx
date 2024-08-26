/* Copyright 2024 Marimo. All rights reserved. */
import { useEffect, useRef, useState } from "react";
import { initializeIslands } from "../initialize";
import { initializePlugins } from "@/plugins/plugins";
import { CellId } from "@/core/cells/ids";
import { Logger } from "@/utils/Logger";
import { CellData } from "@/core/cells/types";

// This will display all the static HTML content.
// We only need to call this once.
initializePlugins();

// #region MarimoIsland

interface MarimoIslandProps {
  /**
   * Code of the cell.
   */
  code: string;
  /**
   * Fallback to render when code is empty.
   */
  children?: React.ReactNode;
  /**
   * Whether the element should be reactive.
   *
   * @default true
   */
  reactive?: boolean;
}

const DEFAULT_APP_ID = "main";

/**
 * Renders a Marimo cell embedded in a React component.
 */
export const MarimoIsland: React.FC<MarimoIslandProps> = (props) => {
  const { code, children, reactive = true } = props;

  // eslint-disable-next-line react/hook-use-state
  const [id] = useState(() => {
    const id = CellId.create();
    initializer.addComponent(id);
    return id;
  });

  useEffect(() => {
    requestAnimationFrame(() => {
      initializer.markMounted(id);
    });
  }, [id]);

  return (
    <marimo-island data-app-id={DEFAULT_APP_ID} data-reactive={reactive}>
      <marimo-cell-output>{children}</marimo-cell-output>
      {code && <marimo-cell-code hidden={true}>{code}</marimo-cell-code>}
    </marimo-island>
  );
};

// #region MarimoEmbeddedApp

interface MarimoEmbeddedAppProps {
  /**
   * Code of the app.
   */
  code: string;
  /**
   * Fallback to render when code is empty.
   */
  children?: React.ReactNode;
}

// #region Initializer

let isInitialized = false;

// Singleton that will wait until all islands are rendered before initializing
// the <marimo-island> elements.
const initializer = {
  islands: new Set<string>(),
  addComponent(id: string) {
    if (isInitialized) {
      Logger.warn(`
⚠️ marimo islands have already been initialized.

You are receiving this warning because you are adding a new island to the DOM
conditionally or after initialization. This is not currently supported.
If you would like to see this supported, please file an issue at https://github.com/marimo-team/marimo/issues
`);
      return;
    }
    this.islands.add(id);
  },
  markMounted(id: string) {
    if (isInitialized) {
      return;
    }

    this.islands.delete(id);

    if (this.islands.size === 0) {
      isInitialized = true;
      Logger.log("Initializing marimo islands...");
      void initializeIslands({}).catch((error) => {
        Logger.error(error);
      });
    }
  },
};

/**
 * Renders a Marimo app embedded in a React component.
 */
export const MarimoEmbeddedApp: React.FC<MarimoEmbeddedAppProps> = (props) => {
  const root = useRef<HTMLDivElement>(null);
  const [cells, setCells] = useState<CellData[]>([]);

  useEffect(() => {
    void initializeIslands({
      onSetCells: (cells) => {
        setCells(cells);
      },
    }).catch((error) => {
      Logger.error(error);
    });
  }, []);

  if (!props.code) {
    return null;
  }

  return (
    <marimo-app data-code={props.code} data-app-id={DEFAULT_APP_ID}>
      {cells.map((cell) => {
        return (
          <marimo-island
            key={cell.id}
            data-app-id={DEFAULT_APP_ID}
            data-cell-id={cell.id}
            data-reactive={true}
          >
            <marimo-cell-output />
          </marimo-island>
        );
      })}
      <div ref={root}>{props.children}</div>
    </marimo-app>
  );
};
