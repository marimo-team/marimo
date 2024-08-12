import { useEffect, useState } from "react";
import { initializeIslands } from "../initialize";
import { initializePlugins } from "@/plugins/plugins";
import { CellId } from "@/core/cells/ids";

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

export const MarimoIsland = (props: MarimoIslandProps) => {
  const { code, children, reactive = true } = props;

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
    <marimo-island
      data-app-id={DEFAULT_APP_ID}
      data-cell-id={id}
      data-reactive={reactive}
    >
      <marimo-cell-output>{children}</marimo-cell-output>
      {code && <marimo-cell-code hidden={true}>{code}</marimo-cell-code>}
    </marimo-island>
  );
};

// #region MarimoIslands

interface MarimoIslandsProps {
  code: string;
  /**
   * Fallback to render when code is empty.
   */
  children?: React.ReactNode;
}

export const MarimoIslands = (props: MarimoIslandsProps) => {
  if (!props.code) {
    return null;
  }

  return (
    <marimo-embed data-code={props.code} data-app-id={DEFAULT_APP_ID}>
      {props.children}
    </marimo-embed>
  );
};

// #region Initializer

// This will display all the static HTML content.
initializePlugins();

let isInitialized = false;

// Singleton that will wait until all islands are rendered before initializing
// the <marimo-island> elements.
const initializer = {
  islands: new Set<string>(),
  addComponent(id: string) {
    if (isInitialized) {
      console.warn(`
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
      void initializeIslands({}).catch((error) => {
        console.error(error);
      });
    }
  },
};
