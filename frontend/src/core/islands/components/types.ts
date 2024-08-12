import type { DOMAttributes } from "react";

type CustomElement<T> = Partial<
  T & DOMAttributes<T> & { children: React.ReactNode; hidden?: boolean }
>;

declare global {
  namespace JSX {
    interface IntrinsicElements {
      /**
       * Island component. This contains the code and output of the cell as children.
       * Each cell has a unique ID and app ID.
       */
      "marimo-island": CustomElement<{
        "data-app-id": string;
        "data-cell-id": string;
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
      "marimo-embed": CustomElement<{
        "data-code": string;
      }>;
    }
  }
}
