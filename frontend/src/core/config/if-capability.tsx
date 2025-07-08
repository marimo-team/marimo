/* Copyright 2024 Marimo. All rights reserved. */

import { useAtomValue } from "jotai";
import React from "react";
import type { Capabilities } from "../kernel/messages";
import { capabilitiesAtom } from "./capabilities";

interface Props {
  capability: keyof Capabilities;
  children: React.ReactNode;
}

export const IfCapability: React.FC<Props> = (props) => {
  const value = useAtomValue(capabilitiesAtom)[props.capability];
  if (value) {
    return props.children;
  }
  return null;
};
