/* Copyright 2023 Marimo. All rights reserved. */
import { PropsWithChildren } from "react";
import {
  ErrorBoundary as ReactErrorBoundary,
  FallbackProps,
} from "react-error-boundary";
import { Button } from "../../ui/button";

export const ErrorBoundary: React.FC<PropsWithChildren> = (props) => {
  return (
    <ReactErrorBoundary FallbackComponent={FallbackComponent}>
      {props.children}
    </ReactErrorBoundary>
  );
};

export const container =
  "flex-1 flex items-center justify-center flex-col space-y-4";

const FallbackComponent: React.FC<FallbackProps> = (props) => {
  return (
    <div className={container}>
      <h1>Something went wrong</h1>
      <p>{props.error?.message}</p>
      <Button onClick={props.resetErrorBoundary} variant="outline">
        Try again
      </Button>
    </div>
  );
};
