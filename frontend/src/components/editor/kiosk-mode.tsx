/* Copyright 2024 Marimo. All rights reserved. */
import { kioskModeAtom } from "@/core/mode";
import { useAtomValue } from "jotai";
import React from "react";

interface Props {
  children: React.ReactNode;
}

export const HideInKioskMode: React.FC<Props> = ({ children }) => {
  const kioskMode = useAtomValue(kioskModeAtom);
  if (kioskMode) {
    return null;
  }
  return children;
};
