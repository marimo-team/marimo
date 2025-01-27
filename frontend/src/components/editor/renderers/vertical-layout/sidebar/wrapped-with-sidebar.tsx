/* Copyright 2024 Marimo. All rights reserved. */
import { cn } from "@/utils/cn";
import type React from "react";
import { SheetMenu } from "./sheet-sidebar";
import { useAtom } from "jotai";
import { sidebarAtom } from "./state";
import { Sidebar } from "./sidebar";
import { useSlot } from "@marimo-team/react-slotz";
import { SlotNames } from "@/core/slots/slots";

interface Props {
  children: React.ReactNode;
}

export const WrappedWithSidebar: React.FC<Props> = ({ children }) => {
  const [{ isOpen, width }, dispatch] = useAtom(sidebarAtom);
  const elements = useSlot(SlotNames.SIDEBAR);

  // Get width from the first sidebar element's dataset
  React.useEffect(() => {
    const firstElement = elements[0];
    if (firstElement) {
      const dataWidth = firstElement.props["data-width"];
      if (dataWidth) {
        dispatch({ type: "setWidth", width: dataWidth });
      }
    }
  }, [elements, dispatch]);

  if (elements.length === 0) {
    return children;
  }

  const normalizedWidth = normalizeWidth(width);
  const closedWidth = "68px";

  return (
    <>
      <Sidebar
        isOpen={isOpen}
        width={width}
        toggle={() => dispatch({ type: "toggle", isOpen: !isOpen })}
      />
      <main
        style={{ marginLeft: isOpen ? normalizedWidth : closedWidth }}
        className={cn(
          "h-full transition-[margin-left] ease-in-out duration-300 overflow-hidden relative lg:block",
          "lg:ml-0",
        )}
      >
        <div className="absolute top-3 left-4 flex items-center z-50">
          <SheetMenu />
        </div>
        {children}
      </main>
    </>
  );
};
