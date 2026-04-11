/* Copyright 2026 Marimo. All rights reserved. */

import { Provider } from "jotai";
import { isValidElement, type JSX } from "react";
import ReactDOM, { type Root } from "react-dom/client";
import { ErrorBoundary } from "@/components/editor/boundary/ErrorBoundary";
import { TooltipProvider } from "@/components/ui/tooltip";
import { notebookAtom } from "@/core/cells/cells";
import { OBJECT_ID_ATTR } from "@/core/dom/ui-element-constants";
import { UI_ELEMENT_REGISTRY } from "@/core/dom/uiregistry";
import { LocaleProvider } from "@/core/i18n/locale-provider";
import { renderHTML } from "@/plugins/core/RenderHTML";
import { invariant } from "@/utils/invariant";
import type { CellId, UIElementId } from "../../cells/ids";
import { store } from "../../state/jotai";
import {
  ISLAND_CSS_CLASSES,
  ISLAND_DATA_ATTRIBUTES,
  ISLAND_TAG_NAMES,
} from "../constants";
import { extractIslandCodeFromEmbed } from "../parse";
import { MarimoOutputWrapper } from "./output-wrapper";

/**
 * Configuration for rendering a marimo island
 */
export interface IslandRenderConfig {
  html: string;
  codeCallback: () => string;
  editor: JSX.Element | null;
  cellId: CellId | undefined;
}

/**
 * A custom element that renders the output of a marimo cell.
 *
 * This web component wraps marimo cell outputs and provides interactive
 * functionality like re-running cells and copying code.
 */
export class MarimoIslandElement extends HTMLElement {
  private root?: Root;

  public static readonly tagName = ISLAND_TAG_NAMES.ISLAND;
  public static readonly outputTagName = ISLAND_TAG_NAMES.CELL_OUTPUT;
  public static readonly codeTagName = ISLAND_TAG_NAMES.CELL_CODE;
  public static readonly editorTagName = ISLAND_TAG_NAMES.CODE_EDITOR;
  public static readonly styleNamespace = ISLAND_CSS_CLASSES.NAMESPACE;

  constructor() {
    super();
    this.classList.add(MarimoIslandElement.styleNamespace);
  }

  /**
   * Gets the app ID from the element's data attribute
   */
  get appId(): string {
    const appId = this.getAttribute(ISLAND_DATA_ATTRIBUTES.APP_ID);
    invariant(appId, "Missing data-app-id attribute");
    return appId;
  }

  /**
   * Whether this island is reactive (has code sent to Python for execution)
   */
  get isReactive(): boolean {
    return this.getAttribute(ISLAND_DATA_ATTRIBUTES.REACTIVE) === "true";
  }

  /**
   * Gets the cell ID by looking up the cell index in the notebook state.
   * Returns undefined for non-reactive islands (they have no corresponding cell).
   */
  get cellId(): CellId | undefined {
    const cellId = this.getAttribute(ISLAND_DATA_ATTRIBUTES.CELL_ID);
    if (cellId) {
      return cellId as CellId;
    }

    const cellIdx = this.getAttribute(ISLAND_DATA_ATTRIBUTES.CELL_IDX);
    if (!cellIdx) {
      return undefined;
    }
    return this.getCellIdFromIndex(Number.parseInt(cellIdx, 10));
  }

  /**
   * Gets the code for this island cell
   */
  get code(): string {
    return extractIslandCodeFromEmbed(this);
  }

  /**
   * Looks up a cell ID from the notebook state by index
   */
  private getCellIdFromIndex(idx: number): CellId {
    const { cellIds } = store.get(notebookAtom);
    const cellId = cellIds.inOrderIds.at(idx);
    invariant(cellId, `Missing cell ID at index ${idx}`);
    return cellId;
  }

  /**
   * Called when the element is added to the DOM.
   *
   * Deferred to a microtask because `defineCustomElement` during
   * `kernel-ready` upgrades all existing elements synchronously,
   * which can happen inside a React render cycle. Rendering
   * synchronously from there causes "unmount during render" warnings.
   */
  connectedCallback(): void {
    // Capture config synchronously (before children get cleared by createRoot)
    const config = this.extractRenderConfig();
    queueMicrotask(() => {
      // Guard against disconnect between connectedCallback and microtask
      if (!this.isConnected) {
        return;
      }
      this.root = ReactDOM.createRoot(this);
      this.renderIsland(config);
    });
  }

  /**
   * Extracts configuration needed for rendering
   */
  private extractRenderConfig(): IslandRenderConfig {
    const output = this.querySelectorOrThrow(MarimoIslandElement.outputTagName);
    const initialOutput = output.innerHTML;
    const optionalEditor = this.getOptionalEditor();
    const code = this.code;
    const cellId = this.cellId;

    // Read objectId directly from the DOM before createRoot clears children.
    // optionalEditor is a <RenderHTML> wrapper, so its .props don't carry the
    // underlying element's attributes — we must grab objectId here instead.
    const editorElement = this.querySelector(MarimoIslandElement.editorTagName);
    const editorObjectId = (
      editorElement?.parentElement as Element | null
    )?.getAttribute(OBJECT_ID_ATTR) as UIElementId | null;

    const codeCallback: () => string =
      optionalEditor && editorObjectId
        ? () => {
            const val = UI_ELEMENT_REGISTRY.lookupValue(editorObjectId);
            return val !== undefined ? String(val) : code;
          }
        : () => code;

    return {
      html: initialOutput,
      codeCallback,
      editor: optionalEditor,
      cellId,
    };
  }

  /**
   * Renders the island with React
   */
  private renderIsland(config: IslandRenderConfig): void {
    const { html, codeCallback, editor, cellId } = config;
    const alwaysShowRun = !!editor;
    const trimmedHtml = html.trim();
    const isEmpty = trimmedHtml === "<span></span>" || trimmedHtml === "";
    const initialHtml = isEmpty ? null : renderHTML({ html: trimmedHtml });

    // Non-reactive islands have no cell in the kernel — just render static HTML
    if (!cellId) {
      this.root?.render(
        <ErrorBoundary>
          <Provider store={store}>
            <LocaleProvider>{initialHtml}</LocaleProvider>
          </Provider>
        </ErrorBoundary>,
      );
      return;
    }

    this.root?.render(
      <ErrorBoundary>
        <Provider store={store}>
          <LocaleProvider>
            <TooltipProvider>
              <MarimoOutputWrapper
                cellId={cellId}
                codeCallback={codeCallback}
                alwaysShowRun={alwaysShowRun}
              >
                {initialHtml}
              </MarimoOutputWrapper>
              {editor}
            </TooltipProvider>
          </LocaleProvider>
        </Provider>
      </ErrorBoundary>,
    );
  }

  /**
   * Attempts to find and render an optional code editor.
   *
   * The DOM structure is:
   *   <marimo-cell-output>
   *     <div data-marimo-element> ← parent wrapper from Python render
   *       <marimo-code-editor .../>
   *     </div>
   *   </marimo-cell-output>
   *
   * We take the parent's outerHTML (the wrapper div) so that the rendered
   * React element includes the UI element registration attributes.
   *
   * @returns A React element for the editor, or null if not found
   */
  private getOptionalEditor(): JSX.Element | null {
    const optionalElement = this.querySelector(
      MarimoIslandElement.editorTagName,
    );
    const html = (optionalElement?.parentNode as Element)?.outerHTML;
    if (html) {
      // Convert HTML to virtual DOM
      const virtualDom = renderHTML({ html });
      // Verify it's a valid React element
      if (isValidElement(virtualDom)) {
        return virtualDom;
      }
    }
    return null;
  }

  /**
   * Queries for an element and throws if not found
   */
  private querySelectorOrThrow(selector: string): Element {
    const element = this.querySelector(selector);
    invariant(element, `Missing ${selector} element`);
    return element;
  }

  /**
   * Cleanup when element is removed from DOM
   */
  disconnectedCallback(): void {
    const root = this.root;
    this.root = undefined;
    // Defer unmount to avoid "unmount during render" race
    if (root) {
      queueMicrotask(() => root.unmount());
    }
  }
}
