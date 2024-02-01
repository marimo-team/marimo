/* Copyright 2024 Marimo. All rights reserved. */
import { onLCP, onFID, onCLS, Metric } from "web-vitals";
import { Logger } from "./Logger";

export function reportVitals() {
  Logger.log("Reporting vitals");
  const logMetric = (metric: Metric) => {
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
  onFID(logMetric);
  onLCP(logMetric);
}
