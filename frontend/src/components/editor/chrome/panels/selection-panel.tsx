/* Copyright 2024 Marimo. All rights reserved. */

import { SlotNames } from "@/core/slots/slots";
import { Fill, Slot } from "@marimo-team/react-slotz";
import type { PropsWithChildren } from "react";

export const DataSelectionPanelSlot: React.FC = () => {
  return <Slot name={SlotNames.DATA_SELECTION} />;
};

export const DataSelectionItem: React.FC<PropsWithChildren> = ({
  children,
}) => {
  return <Fill name={SlotNames.DATA_SELECTION}>{children}</Fill>;
};
