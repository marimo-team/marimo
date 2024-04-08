/* Copyright 2024 Marimo. All rights reserved. */
import { PropsWithChildren } from "react";
import {
  ErrorBoundary as ReactErrorBoundary,
  FallbackProps,
} from "react-error-boundary";
import { Button } from "../../ui/button";
import { Constants } from "@/core/constants";

export const ErrorBoundary: React.FC<PropsWithChildren> = (props) => {
  return (
    <ReactErrorBoundary FallbackComponent={FallbackComponent}>
      {props.children}
    </ReactErrorBoundary>
  );
};

const FallbackComponent: React.FC<FallbackProps> = (props) => {
  return (
    <div className="flex-1 flex items-center justify-center flex-col space-y-4 max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold">Something went wrong</h1>
      <pre className="text-xs bg-muted/40 border rounded-md p-4 max-w-[80%] whitespace-normal">
        {props.error?.message}
      </pre>
      <div>
        If this is an issue with marimo, please report it on{" "}
        <a
          href={Constants.issuesPage}
          target="_blank"
          rel="noreferrer"
          className="underline"
        >
          GitHub
        </a>
        .
      </div>
      <Button
        data-testid="reset-error-boundary-button"
        onClick={props.resetErrorBoundary}
        variant="outline"
      >
        Try again
      </Button>
    </div>
  );
};
