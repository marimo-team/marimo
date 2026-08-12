/* Copyright 2026 Marimo. All rights reserved. */

import { useAtomValue } from "jotai";
import type { ReactNode } from "react";
import { I18nProvider } from "react-aria-components";
import { localeAtom } from "@/core/config/config";
import { safeLocale } from "./locale";

interface LocaleProviderProps {
  children: ReactNode;
}

export const LocaleProvider = ({ children }: LocaleProviderProps) => {
  const locale = useAtomValue(localeAtom);

  return <I18nProvider locale={safeLocale(locale)}>{children}</I18nProvider>;
};
