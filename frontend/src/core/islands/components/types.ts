/* Copyright 2024 Marimo. All rights reserved. */
import type { DOMAttributes } from "react";

type CustomElement<T> = Partial<
  T &
    DOMAttributes<T> & {
      children: React.ReactNode;
      hidden?: boolean;
      key?: string;
    }
>;

declare global {
  // eslint-disable-next-line @typescript-eslint/no-namespace
  namespace JSX {
    interface IntrinsicElements {
      /**
       * Island component. This contains the code and output of the cell as children.
       * Each cell has a unique ID and app ID.
       */
      "marimo-island": CustomElement<{
        "data-app-id": string;
        "data-cell-idx": string;
        "data-reactive": boolean;
      }>;
      /**
       * Output of the cell.
       */
      "marimo-cell-output": CustomElement<{}>;
      /**
       * Code of the cell.
       */
      "marimo-cell-code": CustomElement<{}>;

      /**
       * marimo-embed component. This contains the code for a full marimo application.
       */
      "marimo-app": CustomElement<{
        "data-code": string;
        "data-app-id": string;
      }>;
    }
  }
}
