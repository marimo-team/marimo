/* Copyright 2024 Marimo. All rights reserved. */

import type { ReactNode } from "react";
import { I18nProvider } from "react-aria-components";

interface LocaleProviderProps {
  children: ReactNode;
}

export const LocaleProvider = ({ children }: LocaleProviderProps) => {
  return <I18nProvider>{children}</I18nProvider>;
};
