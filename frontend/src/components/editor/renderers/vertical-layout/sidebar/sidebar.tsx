/* Copyright 2024 Marimo. All rights reserved. */
import { cn } from "@/utils/cn";
import { SidebarToggle } from "./toggle";
import { SidebarSlot } from "./sidebar-slot";
import "./sidebar.css";

interface SidebarProps {
  isOpen: boolean;
  toggle: () => void;
}

export const Sidebar = ({ isOpen, toggle }: SidebarProps) => {
  return (
    <aside
      data-expanded={isOpen}
      className={cn(
        "app-sidebar auto-collapse-nav",
        "absolute top-0 left-0 z-20 h-full -translate-x-full lg:translate-x-0 transition-[width] ease-in-out duration-300",
        // These values need to match wrapped-with-sidebar.tsx
        isOpen ? "w-72" : "w-[68px]",
      )}
    >
      <SidebarToggle isOpen={isOpen} toggle={toggle} />
      <div className="relative h-full flex flex-col px-3 pb-16 pt-14 overflow-y-auto shadow-sm border-l">
        <SidebarSlot />
      </div>
    </aside>
  );
};
