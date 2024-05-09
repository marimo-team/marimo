/* Copyright 2024 Marimo. All rights reserved. */
import { MenuIcon } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import { SidebarSlot } from "./sidebar-slot";

export const SheetMenu = () => {
  return (
    <Sheet>
      <SheetTrigger className="lg:hidden" asChild={true}>
        <Button variant="ghost" className="bg-background">
          <MenuIcon className="w-5 h-5" />
        </Button>
      </SheetTrigger>
      <SheetContent
        className="w-full max-w-72 px-3 h-full flex flex-col"
        side="left"
      >
        <SidebarSlot />
      </SheetContent>
    </Sheet>
  );
};
