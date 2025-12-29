/* Copyright 2026 Marimo. All rights reserved. */
import { ScopeProvider } from "jotai-scope";
import { cellSelectionStateAtom } from "./atoms";

export const CellSelectionProvider = ({
  children,
}: {
  children: React.ReactNode;
}) => {
  return (
    <ScopeProvider atoms={[cellSelectionStateAtom]}>{children}</ScopeProvider>
  );
};
