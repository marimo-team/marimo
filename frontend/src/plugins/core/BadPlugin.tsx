/* Copyright 2023 Marimo. All rights reserved. */
import { ZodError } from "zod";
import { Alert } from "../../components/ui/alert";
import { AlertTitle } from "../../components/ui/alert";

interface Props {
  error: ZodError | Error;
}

export const BadPluginData: React.FC<Props> = ({ error }) => {
  if (error instanceof ZodError) {
    return (
      <Alert variant="destructive">
        <AlertTitle>Bad Data</AlertTitle>
        <div className="text-md">
          <ul>
            {error.issues.map((issue) => {
              const path = issue.path.join(".");
              return (
                <li key={path}>
                  <span className="font-bold">{path}</span>: {issue.message}
                </li>
              );
            })}
          </ul>
        </div>
      </Alert>
    );
  }

  return <div>{error.message}</div>;
};

export function renderError(error: ZodError | Error): JSX.Element {
  return <BadPluginData error={error} />;
}
