/* Copyright 2024 Marimo. All rights reserved. */
import React from "react";
import { Capabilities } from "../kernel/messages";
import { useAtomValue } from "jotai";
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
