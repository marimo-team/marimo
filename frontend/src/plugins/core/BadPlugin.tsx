/* Copyright 2024 Marimo. All rights reserved. */
import { ZodError } from "zod";
import { Alert } from "../../components/ui/alert";
import { AlertTitle } from "../../components/ui/alert";
import {
  Accordion,
  AccordionItem,
  AccordionTrigger,
  AccordionContent,
} from "@radix-ui/react-accordion";
import { JsonOutput } from "@/components/editor/output/JsonOutput";
import { EmotionCacheProvider } from "@/components/editor/output/EmotionCacheProvider";

interface Props {
  error: ZodError | Error;
  shadowRoot: ShadowRoot | null;
  badData: Record<string, unknown>;
}

export const BadPluginData: React.FC<Props> = ({
  error,
  badData,
  shadowRoot,
}) => {
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
        <Accordion type="single" collapsible={true}>
          <AccordionItem
            value="item-1"
            className="text-muted-foreground border-muted-foreground-20"
          >
            <AccordionTrigger className="py-2 text-[0.84375rem]">
              View Data:
            </AccordionTrigger>
            <AccordionContent className="text-[0.84375rem]">
              <EmotionCacheProvider container={shadowRoot}>
                <JsonOutput data={badData} />
              </EmotionCacheProvider>
            </AccordionContent>
          </AccordionItem>
        </Accordion>
      </Alert>
    );
  }

  return <div>{error.message}</div>;
};

export function renderError(
  error: ZodError | Error,
  badData: Record<string, unknown>,
  shadowRoot: ShadowRoot | null,
): JSX.Element {
  return (
    <BadPluginData error={error} badData={badData} shadowRoot={shadowRoot} />
  );
}
