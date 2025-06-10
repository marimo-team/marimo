/* Copyright 2024 Marimo. All rights reserved. */
import { invariant } from "@/utils/invariant";
import type { CellId } from "../../cells/ids";
import { store } from "../../state/jotai";
import ReactDOM, { type Root } from "react-dom/client";
import { isValidElement, type JSX } from "react";
import { extractIslandCodeFromEmbed } from "../parse";
import { MarimoOutputWrapper } from "./output-wrapper";
import { Provider } from "jotai";
import { renderHTML } from "@/plugins/core/RenderHTML";
import { TooltipProvider } from "@/components/ui/tooltip";
import { ErrorBoundary } from "@/components/editor/boundary/ErrorBoundary";
import { UI_ELEMENT_REGISTRY } from "@/core/dom/uiregistry";
import { notebookAtom } from "@/core/cells/cells";

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
    const cellId = cellIds.inOrderIds.at(idx);
    invariant(cellId, "Missing cell ID");
    return cellId;
  }

  get code(): string {
    return extractIslandCodeFromEmbed(this);
  }

  connectedCallback() {
    const output = this.querySelectorOrThrow(MarimoIslandElement.outputTagName);
    const initialOutput = output.innerHTML;

    const optionalEditor = this.getOptionalEditor();
    const code = this.code;
    const codeCallback: () => string = optionalEditor
      ? () =>
          `${UI_ELEMENT_REGISTRY.lookupValue(
            optionalEditor.props["object-id"],
          )}`
      : () => code;

    this.root = ReactDOM.createRoot(this);
    this.render(initialOutput, codeCallback, optionalEditor);
  }

  private render(
    html: string,
    codeCallback: () => string,
    editor: JSX.Element | null,
  ) {
    const alwaysShowRun = !!editor;
    html = html.trim();
    const isEmpty = html === "<span></span>" || html === "";
    const initialHtml = isEmpty ? null : renderHTML({ html });

    this.root?.render(
      <ErrorBoundary>
        <Provider store={store}>
          <TooltipProvider>
            <MarimoOutputWrapper
              cellId={this.cellId}
              codeCallback={codeCallback}
              alwaysShowRun={alwaysShowRun}
            >
              {initialHtml}
            </MarimoOutputWrapper>
            {editor}
          </TooltipProvider>
        </Provider>
      </ErrorBoundary>,
    );
  }

  private getOptionalEditor(): JSX.Element | null {
    // TODO: Maybe add specificity with a [editor=island] selector or something.
    const optionalElement = this.querySelector(
      MarimoIslandElement.editorTagName,
    );
    const html = (optionalElement?.parentNode as Element)?.outerHTML;
    if (html) {
      // Push back to virtual dom.
      const virtualDom = renderHTML({ html });
      // and prove that it's an element.
      if (isValidElement(virtualDom)) {
        return virtualDom;
      }
    }
    return null;
  }

  private querySelectorOrThrow(selector: string) {
    const element = this.querySelector(selector);
    invariant(element, `Missing ${selector} element`);
    return element;
  }
}
