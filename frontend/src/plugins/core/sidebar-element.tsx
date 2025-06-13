/* Copyright 2024 Marimo. All rights reserved. */

import { init } from "@paralleldrive/cuid2";
import { sidebarAtom } from "@/components/editor/renderers/vertical-layout/sidebar/state";
import { defineCustomElement } from "@/core/dom/defineCustomElement";
import { SlotNames, slotsController } from "@/core/slots/slots";
import { store } from "@/core/state/jotai";
import { Logger } from "@/utils/Logger";
import { renderHTML } from "./RenderHTML";

const createId = init({ length: 6 });

/**
 * This is a custom DOM element that will be used to portal
 * it's children to a React component sidebar.
 */
export function initializeSidebarElement(): void {
  const SidebarComponent = class extends HTMLElement {
    private observer?: MutationObserver;
    private uniqueId = Symbol(createId());

    connectedCallback() {
      // Render the component for the first time
      this.mountReactComponent();

      // This observer is used to detect changes to the children and re-render the component
      this.observer = new MutationObserver(() => {
        this.updateReactComponent();
      });

      this.style.display = "none";

      // Listen for DOM changes
      this.observer.observe(this, {
        attributes: true,
        childList: true,
        subtree: true,
        characterData: true,
      });
    }

    disconnectedCallback() {
      if (this.observer) {
        this.observer.disconnect();
        this.unmountReactComponent();
      }
    }

    private mountReactComponent() {
      this.syncWidth();
      slotsController.mount({
        name: SlotNames.SIDEBAR,
        ref: this.uniqueId,
        children: this.getContents(),
      });
    }

    private unmountReactComponent() {
      slotsController.unmount({
        name: SlotNames.SIDEBAR,
        ref: this.uniqueId,
      });
    }

    private updateReactComponent() {
      this.syncWidth();
      slotsController.update({
        name: SlotNames.SIDEBAR,
        ref: this.uniqueId,
        children: this.getContents(),
      });
    }

    // Grab the data-width attribute from the element and set the width in the store
    // This is used to set the width of the sidebar when it is opened
    private syncWidth(): void {
      try {
        const width = this.dataset.width;
        if (width) {
          store.set(sidebarAtom, {
            type: "setWidth",
            width: JSON.parse(width) as string,
          });
        } else {
          store.set(sidebarAtom, {
            type: "setWidth",
            width: undefined,
          });
        }
      } catch (error) {
        Logger.error(error);
      }
    }

    /**
     * Get the children of the element as React nodes.
     */
    private getContents(): React.ReactNode {
      return renderHTML({ html: this.innerHTML });
    }
  };

  defineCustomElement("marimo-sidebar", SidebarComponent);
}
