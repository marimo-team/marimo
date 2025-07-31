/* Copyright 2024 Marimo. All rights reserved. */
import { Logger } from "./Logger";

export async function reportVitals() {
  if (typeof document === "undefined") {
    return;
  }

  const { onLCP, onINP, onCLS } = await import("web-vitals");
  Logger.log("Reporting vitals");
  const logMetric = (metric: {
    name: string;
    value: number;
    rating: string;
  }) => {
    const color =
      metric.rating === "good"
        ? "green"
        : metric.rating === "needs-improvement"
          ? "orange"
          : "red";
    Logger.log(
      `%c [Metric ${metric.name}] ${metric.value}`,
      `background:${color}; color:white; padding:2px 0; border-radius:2px`,
    );
  };
  onCLS(logMetric);
  onINP(logMetric);
  onLCP(logMetric);
}
