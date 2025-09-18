/* Copyright 2024 Marimo. All rights reserved. */

import { useAtomValue } from "jotai";
import type { ReactNode } from "react";
import { I18nProvider } from "react-aria-components";
import { localeAtom } from "@/core/config/config";

interface LocaleProviderProps {
  children: ReactNode;
}

export const LocaleProvider = ({ children }: LocaleProviderProps) => {
  const locale = useAtomValue(localeAtom);

  // If locale is null or undefined, let React Aria auto-detect
  if (!locale) {
    return <I18nProvider>{children}</I18nProvider>;
  }

  return <I18nProvider locale={locale}>{children}</I18nProvider>;
};
