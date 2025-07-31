/* Copyright 2024 Marimo. All rights reserved. */

import { useAtomValue } from "jotai";
import React from "react";
import { kioskModeAtom } from "@/core/mode";

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

export const ShowInKioskMode: React.FC<Props> = ({ children }) => {
  const kioskMode = useAtomValue(kioskModeAtom);
  if (kioskMode) {
    return children;
  }
  return null;
};
