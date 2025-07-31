/* Copyright 2024 Marimo. All rights reserved. */
import { cn } from "@/utils/cn";
import { SidebarSlot } from "./sidebar-slot";
import { CLOSED_WIDTH } from "./state";
import { SidebarToggle } from "./toggle";
import "./sidebar.css";

interface SidebarProps {
  isOpen: boolean;
  toggle: () => void;
  width?: string | number;
}

export const Sidebar = ({ isOpen, toggle, width }: SidebarProps) => {
  return (
    <aside
      data-expanded={isOpen}
      style={{ width: isOpen ? width : CLOSED_WIDTH }}
      className={cn(
        "app-sidebar auto-collapse-nav",
        "top-0 left-0 z-20 h-full hidden lg:block relative transition-[width] ease-in-out duration-300",
      )}
    >
      <SidebarToggle isOpen={isOpen} toggle={toggle} />
      <div className="relative h-full flex flex-col px-3 pb-16 pt-14 overflow-y-auto shadow-sm border-l">
        <SidebarSlot />
      </div>
    </aside>
  );
};
