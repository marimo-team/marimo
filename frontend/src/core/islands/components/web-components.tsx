/* Copyright 2024 Marimo. All rights reserved. */
import { invariant } from "@/utils/invariant";
import type { CellId } from "../../cells/ids";
import { store } from "../../state/jotai";
import { notebookAtom } from "../../cells/cells";
import ReactDOM, { type Root } from "react-dom/client";
import { isValidElement } from "react";
import { extractIslandCodeFromEmbed } from "../parse";
import { MarimoOutputWrapper } from "./output-wrapper";
import { Provider } from "jotai";
import { renderHTML } from "@/plugins/core/RenderHTML";
import { TooltipProvider } from "@/components/ui/tooltip";
import { ErrorBoundary } from "@/components/editor/boundary/ErrorBoundary";
import { UI_ELEMENT_REGISTRY } from "@/core/dom/uiregistry";
import { MarimoIslandConstants } from "./constants";

/**
 * A custom element that renders the output of a marimo cell
 */
export class MarimoIslandElement extends HTMLElement {
  private root?: Root;

  constructor() {
    super();
    this.classList.add(MarimoIslandConstants.styleNamespace);
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
    return cellIds.atOrThrow(idx);
  }

  get code(): string {
    return extractIslandCodeFromEmbed(this);
  }

  connectedCallback() {
    const output = this.querySelectorOrThrow(
      MarimoIslandConstants.outputTagName,
    );
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
    this.root?.render(
      <ErrorBoundary>
        <Provider store={store}>
          <TooltipProvider>
            <MarimoOutputWrapper
              cellId={this.cellId}
              codeCallback={codeCallback}
              alwaysShowRun={alwaysShowRun}
            >
              {renderHTML({ html })}
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
      MarimoIslandConstants.editorTagName,
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
