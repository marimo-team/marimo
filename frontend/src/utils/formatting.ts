/* Copyright 2024 Marimo. All rights reserved. */

import { prettyNumber } from "./numbers";

/**
 * Format bytes to human-readable format
 * @param bytes - Number of bytes to format
 * @param locale - Optional locale for number formatting
 * @returns Formatted string (e.g., "1.5 MB")
 */
export function formatBytes(bytes: number, locale: string): string {
  if (bytes === 0 || bytes === -1) {
    return "0 B";
  }
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB", "TB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  const value = bytes / k ** i;
  return `${prettyNumber(value, locale)} ${sizes[i]}`;
}

/**
 * Format seconds to human-readable time format
 * @param seconds - Number of seconds to format
 * @param locale - Optional locale for number formatting
 * @returns Formatted string (e.g., "1m 30s", "2h 15m", "500ms", "100µs")
 */
export function formatTime(seconds: number, locale: string): string {
  if (seconds === 0) {
    return "0s";
  }
  if (seconds < 0.001) {
    return `${prettyNumber(seconds * 1_000_000, locale)}µs`;
  }
  if (seconds < 1) {
    return `${prettyNumber(seconds * 1000, locale)}ms`;
  }
  if (seconds < 60) {
    return `${prettyNumber(seconds, locale)}s`;
  }
  const minutes = Math.floor(seconds / 60);
  const secs = seconds % 60;
  if (minutes < 60) {
    return secs > 0
      ? `${minutes}m ${prettyNumber(secs, locale)}s`
      : `${minutes}m`;
  }
  const hours = Math.floor(minutes / 60);
  const remainingMins = minutes % 60;
  return remainingMins > 0 ? `${hours}h ${remainingMins}m` : `${hours}h`;
}
