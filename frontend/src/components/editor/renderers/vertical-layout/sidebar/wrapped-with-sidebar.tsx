/* Copyright 2024 Marimo. All rights reserved. */
import { cn } from "@/utils/cn";
import React from "react";
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
  const [{ isOpen }, dispatch] = useAtom(sidebarAtom);
  const elements = useSlot(SlotNames.SIDEBAR);

  if (elements.length === 0) {
    return children;
  }

  return (
    <>
      <Sidebar
        isOpen={isOpen}
        toggle={() => dispatch({ type: "toggle", isOpen: !isOpen })}
      />
      <main
        className={cn(
          "h-full transition-[margin-left] ease-in-out duration-300 overflow-hidden relative",
          // These values need to match sidebar.tsx
          isOpen ? "lg:ml-72" : "lg:ml-[68px]",
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
