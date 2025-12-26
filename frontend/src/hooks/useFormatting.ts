/* Copyright 2026 Marimo. All rights reserved. */

import { useCallback } from "react";
import { useLocale } from "react-aria";
import { getShortTimeZone, prettyDate, timeAgo } from "@/utils/dates";
import {
  prettyEngineeringNumber,
  prettyNumber,
  prettyScientificNumber,
} from "@/utils/numbers";

/**
 * Hook that provides locale-aware number formatting using the prettyNumber utility
 */
export function usePrettyNumber() {
  const { locale } = useLocale();

  return useCallback(
    (value: unknown): string => {
      return prettyNumber(value, locale);
    },
    [locale],
  );
}

/**
 * Hook that provides locale-aware scientific number formatting
 */
export function usePrettyScientificNumber() {
  const { locale } = useLocale();

  return useCallback(
    (value: number, opts: { shouldRound?: boolean } = {}): string => {
      return prettyScientificNumber(value, { ...opts, locale });
    },
    [locale],
  );
}

/**
 * Hook that provides locale-aware engineering number formatting
 */
export function usePrettyEngineeringNumber() {
  const { locale } = useLocale();

  return useCallback(
    (value: number): string => {
      return prettyEngineeringNumber(value, locale);
    },
    [locale],
  );
}

/**
 * Hook that provides locale-aware date formatting
 */
export function usePrettyDate() {
  const { locale } = useLocale();

  return useCallback(
    (
      value: string | number | null | undefined,
      type: "date" | "datetime",
    ): string => {
      return prettyDate(value, type, locale);
    },
    [locale],
  );
}

/**
 * Hook that provides locale-aware relative time formatting
 */
export function useTimeAgo() {
  const { locale } = useLocale();

  return useCallback(
    (value: string | number | null | undefined): string => {
      return timeAgo(value, locale);
    },
    [locale],
  );
}

/**
 * Hook that provides locale-aware timezone abbreviation
 */
export function useShortTimeZone() {
  const { locale } = useLocale();

  return useCallback(
    (timezone: string): string => {
      return getShortTimeZone(timezone, locale);
    },
    [locale],
  );
}
