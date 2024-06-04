/* Copyright 2024 Marimo. All rights reserved. */
import React from "react";

interface Props {
  milliseconds: number;
  children: React.ReactNode;
  fallback?: React.ReactNode;
}

export const DelayMount = ({ milliseconds, children, fallback }: Props) => {
  const [mounted, setMounted] = React.useState(false);

  React.useEffect(() => {
    const timeout = setTimeout(() => {
      setMounted(true);
    }, milliseconds);

    return () => {
      clearTimeout(timeout);
    };
  }, [milliseconds]);

  return mounted ? children : fallback;
};
