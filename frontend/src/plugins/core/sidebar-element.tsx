/* Copyright 2024 Marimo. All rights reserved. */
import { defineCustomElement } from "@/core/dom/defineCustomElement";
import { renderHTML } from "./RenderHTML";
import { SlotNames, slotsController } from "@/core/slots/slots";
import { init } from "@paralleldrive/cuid2";

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
      slotsController.update({
        name: SlotNames.SIDEBAR,
        ref: this.uniqueId,
        children: this.getContents(),
      });
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
