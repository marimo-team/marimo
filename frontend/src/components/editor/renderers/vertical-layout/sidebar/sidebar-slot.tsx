/* Copyright 2024 Marimo. All rights reserved. */

import { Slot } from "@marimo-team/react-slotz";
import React, { memo } from "react";
import { SlotNames } from "@/core/slots/slots";

export const SidebarSlot: React.FC = memo(() => {
  return <Slot name={SlotNames.SIDEBAR} />;
});
SidebarSlot.displayName = "SidebarSlot";
