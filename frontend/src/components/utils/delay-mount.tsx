/* Copyright 2024 Marimo. All rights reserved. */
import { useIntersectionObserver } from "@uidotdev/usehooks";
import React, { useEffect, useState } from "react";

interface Props {
  /**
   * The delay in milliseconds before mounting the children.
   */
  milliseconds: number;

  /**
   * The content to be rendered after the delay.
   */
  children: React.ReactNode;

  /**
   * The content to be rendered while waiting for the delay or visibility condition.
   */
  fallback?: React.ReactNode;

  /**
   * If true, the children will only be rendered if the component has been visible in the viewport at least once.
   */
  visibility?: boolean;

  /**
   * The threshold at which the visibility is considered. A number between 0 and 1.
   */
  threshold?: number;

  /**
   * The root margin for the intersection observer.
   */
  rootMargin?: string;
}

/**
 * DelayMount component delays the rendering of its children until a specified time has passed.
 * It can also conditionally render based on the visibility of the component in the viewport.
 */
export const DelayMount = ({
  milliseconds,
  children,
  fallback,
  visibility = false,
  threshold = 0,
  rootMargin = "0px",
}: Props) => {
  const [mounted, setMounted] = useState(false);
  const [hasBeenVisible, setHasBeenVisible] = useState(false);
  const [ref, entry] = useIntersectionObserver({
    threshold,
    root: null,
    rootMargin,
  });

  useEffect(() => {
    if (entry?.isIntersecting) {
      setHasBeenVisible(true);
    }
  }, [entry?.isIntersecting]);

  useEffect(() => {
    const timeout = setTimeout(() => {
      setMounted(true);
    }, milliseconds);

    return () => {
      clearTimeout(timeout);
    };
  }, [milliseconds]);

  // Determine if the children should be shown
  // If visibility is true, only show the children if the component has been visible in the viewport at least once.
  // If visibility is false, always show the children after the delay.
  const shouldShow = visibility && !hasBeenVisible ? false : mounted;

  return (
    <div ref={visibility ? ref : null} className="contents">
      {shouldShow ? children : fallback}
    </div>
  );
};
