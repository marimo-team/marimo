/* Copyright 2026 Marimo. All rights reserved. */
import React, {
  Activity,
  type ActivityProps,
  type PropsWithChildren,
} from "react";

interface Props {
  isOpen: boolean;
}

interface LazyActivityProps extends ActivityProps {
  /**
   * Fully unmount the children when hidden instead of preserving their state.
   * Use this for imperative components that cannot survive Activity's effect
   * teardown while hidden.
   */
  unmountOnHide?: boolean;
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
export const LazyActivity: React.FC<PropsWithChildren<LazyActivityProps>> = (
  props,
) => {
  const [hasMountedBefore, setHasMountedBefore] = React.useState(false);

  if (props.mode === "visible" && !hasMountedBefore) {
    setHasMountedBefore(true);
  }

  if (props.unmountOnHide && props.mode === "hidden") {
    return null;
  }

  if (hasMountedBefore) {
    const { unmountOnHide: _, ...activityProps } = props;
    return <Activity {...activityProps} />;
  }

  return null;
};
