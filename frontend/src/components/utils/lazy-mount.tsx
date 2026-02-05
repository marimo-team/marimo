/* Copyright 2026 Marimo. All rights reserved. */
import React, {
  Activity,
  type ActivityProps,
  type PropsWithChildren,
} from "react";

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
  const [hasMountedBefore, setHasMountedBefore] = React.useState(false);

  if (isOpen && !hasMountedBefore) {
    setHasMountedBefore(true);
  }

  return hasMountedBefore || isOpen ? children : null;
};

/**
 * Wraps a component in an Activity component. It is not mounted until it is open for the first time.
 */
export const LazyActivity: React.FC<PropsWithChildren<ActivityProps>> = (
  props,
) => {
  const [hasMountedBefore, setHasMountedBefore] = React.useState(false);

  if (props.mode === "visible" && !hasMountedBefore) {
    setHasMountedBefore(true);
  }

  if (hasMountedBefore) {
    return <Activity {...props} />;
  }

  return null;
};
