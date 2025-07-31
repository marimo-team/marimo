/* Copyright 2024 Marimo. All rights reserved. */

import { useSlot } from "@marimo-team/react-slotz";
import { useAtom } from "jotai";
import type React from "react";
import { SlotNames } from "@/core/slots/slots";
import { SheetMenu } from "./sheet-sidebar";
import { Sidebar } from "./sidebar";
import { normalizeWidth, sidebarAtom } from "./state";

interface Props {
  children: React.ReactNode;
}

export const WrappedWithSidebar: React.FC<Props> = ({ children }) => {
  const [{ isOpen, width }, dispatch] = useAtom(sidebarAtom);
  const elements = useSlot(SlotNames.SIDEBAR);

  if (elements.length === 0) {
    return children;
  }

  const openWidth = normalizeWidth(width);

  return (
    <div className="inset-0 absolute flex">
      <Sidebar
        isOpen={isOpen}
        width={openWidth}
        toggle={() => dispatch({ type: "toggle", isOpen: !isOpen })}
      />
      <div className="absolute top-3 left-4 flex items-center z-50">
        <SheetMenu openWidth={openWidth} />
      </div>
      {children}
    </div>
  );
};
