/* Copyright 2024 Marimo. All rights reserved. */
import { invariant } from "@/utils/invariant";
import { CellId } from "../../cells/ids";
import { store } from "../../state/jotai";
import { notebookAtom } from "../../cells/cells";
import ReactDOM, { Root } from "react-dom/client";
import { extractIslandCodeFromEmbed } from "../parse";
import { MarimoOutputWrapper } from "./output-wrapper";
import { Provider } from "jotai";
import { renderHTML } from "@/plugins/core/RenderHTML";
import { TooltipProvider } from "@/components/ui/tooltip";
import { ErrorBoundary } from "@/components/editor/boundary/ErrorBoundary";

/**
 * A custom element that renders the output of a marimo cell
 */
export class MarimoIslandElement extends HTMLElement {
  private root?: Root;

  public static readonly tagName = "marimo-island";
  public static readonly outputTagName = "marimo-cell-output";
  public static readonly codeTagName = "marimo-cell-code";
  public static readonly editorTagName = "marimo-code-editor";
  public static readonly styleNamespace = "marimo";

  constructor() {
    super();
    this.classList.add(MarimoIslandElement.styleNamespace);
  }

  get appId(): string {
    invariant(this.dataset.appId, "Missing data-app-id attribute");
    return this.dataset.appId;
  }

  get cellId(): CellId {
    // Get the cell ID from the code
    invariant(this.dataset.cellIdx, "Missing data-cell-idx attribute");
    const { cellIds } = store.get(notebookAtom);
    const idx = Number.parseInt(this.dataset.cellIdx, 10);
    invariant(cellIds[idx], `Cell ID not found for index ${idx}`);
    return cellIds[idx];
  }

  get code(): string {
    return extractIslandCodeFromEmbed(this);
  }

  connectedCallback() {
    const output = this.querySelectorOrThrow(MarimoIslandElement.outputTagName);
    const initialOutput = output.innerHTML;
    this.root = ReactDOM.createRoot(this);
    this.render(initialOutput);
  }

  private render(html: string) {
    this.root?.render(
      <ErrorBoundary>
        <Provider store={store}>
          <TooltipProvider>
            <MarimoOutputWrapper cellId={this.cellId} code={this.code}>
              {renderHTML({ html })}
            </MarimoOutputWrapper>
          </TooltipProvider>
        </Provider>
      </ErrorBoundary>,
    );
  }

  private querySelectorOrThrow(selector: string) {
    const element = this.querySelector(selector);
    invariant(element, `Missing ${selector} element`);
    return element;
  }
}
