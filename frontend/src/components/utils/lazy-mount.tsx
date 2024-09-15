/* Copyright 2024 Marimo. All rights reserved. */
import React, { type PropsWithChildren } from "react";

interface Props {
  isOpen: boolean;
}

/**
 * Lazy-mount until it is open for the first time
 */
export const LazyMount: React.FC<PropsWithChildren<Props>> = ({
  isOpen,
  children,
}) => {
  const [isMounted, setIsMounted] = React.useState(false);

  React.useEffect(() => {
    if (isOpen && !isMounted) {
      setIsMounted(true);
    }
  }, [isOpen, isMounted]);

  return isMounted ? children : null;
};
