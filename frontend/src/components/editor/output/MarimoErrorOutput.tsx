/* Copyright 2024 Marimo. All rights reserved. */

import { cn } from "../../../utils/cn";
import type { MarimoError } from "../../../core/kernel/messages";
import { Alert } from "../../ui/alert";
import { AlertTitle } from "../../ui/alert";

import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { Fragment } from "react";
import { CellLinkError } from "../links/cell-link";
import type { CellId } from "@/core/cells/ids";
import { AutoFixButton } from "../errors/auto-fix";
import { SquareArrowOutUpRightIcon } from "lucide-react";

const Tip = (props: {
  title?: string;
  className?: string;
  children: React.ReactNode;
}): JSX.Element => {
  return (
    <Accordion type="single" collapsible={true} className={props.className}>
      <AccordionItem value="item-1" className="text-muted-foreground">
        <AccordionTrigger className="pt-2 pb-2 font-normal">
          {props.title ?? "Tip"}
        </AccordionTrigger>
        <AccordionContent className="mr-24 text-[0.84375rem]">
          {props.children}
        </AccordionContent>
      </AccordionItem>
    </Accordion>
  );
};

interface Props {
  cellId: CellId | undefined;
  errors: MarimoError[];
  className?: string;
}

/**
 * List of errors due to violations of Marimo semantics.
 */
export const MarimoErrorOutput = ({
  errors,
  cellId,
  className,
}: Props): JSX.Element => {
  let titleContents = "This cell wasn't run because it has errors";
  let alertVariant: "destructive" | "default" = "destructive";
  let titleColor = "text-error";
  const liStyle = "my-0.5 ml-8 text-muted-foreground/40";

  // Check for certain error types to adjust title and appearance
  if (errors.some((e) => e.type === "interruption")) {
    titleContents = "Interrupted";
  } else if (errors.some((e) => e.type === "internal")) {
    titleContents = "An internal error occurred";
  } else if (errors.some((e) => e.type === "ancestor-prevented")) {
    titleContents = "Ancestor prevented from running";
    alertVariant = "default";
    titleColor = "text-muted-foreground";
    titleColor = "text-secondary-foreground";
  } else if (errors.some((e) => e.type === "ancestor-stopped")) {
    titleContents = "Ancestor stopped";
    alertVariant = "default";
    titleColor = "text-secondary-foreground";
  } else {
    // Check for exception type
    const exceptionError = errors.find((e) => e.type === "exception");
    if (exceptionError && "exception_type" in exceptionError) {
      titleContents = exceptionError.exception_type;
    }
  }

  // Group errors by type
  const cycleErrors = errors.filter(
    (e): e is Extract<MarimoError, { type: "cycle" }> => e.type === "cycle",
  );
  const multipleDefsErrors = errors.filter(
    (e): e is Extract<MarimoError, { type: "multiple-defs" }> =>
      e.type === "multiple-defs",
  );
  const importStarErrors = errors.filter(
    (e): e is Extract<MarimoError, { type: "import-star" }> =>
      e.type === "import-star",
  );
  const deleteNonlocalErrors = errors.filter(
    (e): e is Extract<MarimoError, { type: "delete-nonlocal" }> =>
      e.type === "delete-nonlocal",
  );
  const interruptionErrors = errors.filter(
    (e): e is Extract<MarimoError, { type: "interruption" }> =>
      e.type === "interruption",
  );
  const exceptionErrors = errors.filter(
    (e): e is Extract<MarimoError, { type: "exception" }> =>
      e.type === "exception",
  );
  const strictExceptionErrors = errors.filter(
    (e): e is Extract<MarimoError, { type: "strict-exception" }> =>
      e.type === "strict-exception",
  );
  const internalErrors = errors.filter(
    (e): e is Extract<MarimoError, { type: "internal" }> =>
      e.type === "internal",
  );
  const ancestorPreventedErrors = errors.filter(
    (e): e is Extract<MarimoError, { type: "ancestor-prevented" }> =>
      e.type === "ancestor-prevented",
  );
  const ancestorStoppedErrors = errors.filter(
    (e): e is Extract<MarimoError, { type: "ancestor-stopped" }> =>
      e.type === "ancestor-stopped",
  );
  const syntaxErrors = errors.filter(
    (e): e is Extract<MarimoError, { type: "syntax" }> => e.type === "syntax",
  );
  const unknownErrors = errors.filter(
    (e): e is Extract<MarimoError, { type: "unknown" }> => e.type === "unknown",
  );

  const renderMessages = () => {
    const messages: JSX.Element[] = [];

    if (syntaxErrors.length > 0 || unknownErrors.length > 0) {
      messages.push(
        <li key="syntax-unknown">
          {syntaxErrors.map((error, idx) => (
            <p key={`syntax-${idx}`}>{error.msg}</p>
          ))}
          {unknownErrors.map((error, idx) => (
            <p key={`unknown-${idx}`}>{error.msg}</p>
          ))}
          {cellId && (
            <AutoFixButton
              errors={[...syntaxErrors, ...unknownErrors]}
              cellId={cellId}
            />
          )}
        </li>,
      );
    }

    if (cycleErrors.length > 0) {
      messages.push(
        <li key="cycle">
          <p className="text-muted-foreground font-medium">
            This cell is in a cycle.
          </p>
          <ul className="list-disc">
            {cycleErrors.flatMap((error, errorIdx) =>
              error.edges_with_vars.map((edge, edgeIdx) => (
                <li className={liStyle} key={`cycle-${errorIdx}-${edgeIdx}`}>
                  <CellLinkError cellId={edge[0] as CellId} />
                  <span className="text-muted-foreground">
                    {" -> "}
                    {edge[1].length === 1 ? edge[1][0] : edge[1].join(", ")}
                    {" -> "}
                  </span>
                  <CellLinkError cellId={edge[2] as CellId} />
                </li>
              )),
            )}
          </ul>
          {cellId && <AutoFixButton errors={cycleErrors} cellId={cellId} />}
          <Tip
            title="What are cycles and how do I resolve them?"
            className="mb-2"
          >
            <p className="pb-2">
              An example of a cycle is if one cell declares a variable 'a' and
              reads 'b', and another cell declares 'b' and and reads 'a'. Cycles
              like this make it impossible for marimo to know how to run your
              cells, and generally suggest that your code has a bug.
            </p>

            <p className="py-2">
              Try merging these cells into a single cell to eliminate the cycle.
            </p>

            <p className="py-2">
              <a
                className={cn(
                  "cursor-pointer text-[var(--blue-10)] hover:underline",
                )}
                href="https://links.marimo.app/errors-cycles"
                target="_blank"
                rel="noreferrer"
              >
                Learn more at our docs{" "}
                <SquareArrowOutUpRightIcon size="0.75rem" className="inline" />
              </a>
              .
            </p>
          </Tip>
        </li>,
      );
    }

    if (multipleDefsErrors.length > 0) {
      messages.push(
        <li key="multiple-defs">
          <p className="text-muted-foreground font-medium">
            This cell redefines variables from other cells.
          </p>

          {multipleDefsErrors.map((error, idx) => (
            <Fragment key={`multiple-defs-${idx}`}>
              <p className="text-muted-foreground mt-2">{`'${error.name}' was also defined by:`}</p>
              <ul className="list-disc">
                {error.cells.map((cid, cidIdx) => (
                  <li className={liStyle} key={`cell-${cidIdx}`}>
                    <CellLinkError cellId={cid as CellId} />
                  </li>
                ))}
              </ul>
            </Fragment>
          ))}
          {cellId && (
            <AutoFixButton errors={multipleDefsErrors} cellId={cellId} />
          )}
          <Tip title="Why can't I redefine variables?">
            <p className="pb-2">
              marimo requires that each variable is defined in just one cell.
              This constraint enables reactive and reproducible execution,
              arbitrary cell reordering, seamless UI elements, execution as a
              script, and more.
            </p>

            <p className="py-2">
              Try merging this cell with the mentioned cells or wrapping it in a
              function. Alternatively, rename variables to make them private to
              this cell by prefixing them with an underscore.
            </p>

            <p className="py-2">
              <a
                className={cn(
                  "cursor-pointer text-[var(--blue-10)] hover:underline",
                )}
                href="https://links.marimo.app/errors-multiple-definitions"
                target="_blank"
                rel="noreferrer"
              >
                Learn more at our docs{" "}
                <SquareArrowOutUpRightIcon size="0.75rem" className="inline" />
              </a>
              .
            </p>
          </Tip>
        </li>,
      );
    }

    if (importStarErrors.length > 0) {
      messages.push(
        <li key="import-star">
          {importStarErrors.map((error, idx) => (
            <p key={`import-star-${idx}`} className="text-muted-foreground">
              {error.msg}
            </p>
          ))}
          {cellId && (
            <AutoFixButton errors={importStarErrors} cellId={cellId} />
          )}
          <Tip title="Why can't I use `import *`?">
            <p className="pb-2">
              Star imports are incompatible with marimo's git-friendly file
              format and reproducible reactive execution.
            </p>

            <p className="py-2">
              marimo's Python file format stores code in functions, so notebooks
              can be imported as regular Python modules without executing all
              their code. But Python disallows `import *` everywhere except at
              the top-level of a module.
            </p>

            <p className="py-2">
              Star imports would also silently add names to globals, which would
              be incompatible with reactive execution.
            </p>

            <p className="py-2">
              <a
                className={cn(
                  "cursor-pointer text-[var(--blue-10)] hover:underline",
                )}
                href="https://links.marimo.app/errors-import-star"
                target="_blank"
                rel="noreferrer"
              >
                Learn more at our docs{" "}
                <SquareArrowOutUpRightIcon size="0.75rem" className="inline" />
              </a>
              .
            </p>
          </Tip>
        </li>,
      );
    }

    if (deleteNonlocalErrors.length > 0) {
      messages.push(
        <li key="delete-nonlocal">
          {deleteNonlocalErrors.map((error, idx) => (
            <div key={`delete-nonlocal-${idx}`}>
              {`The variable '${error.name}' can't be deleted because it was defined by another cell (`}
              <CellLinkError cellId={error.cells[0] as CellId} />
              {")"}
            </div>
          ))}
          {cellId && (
            <AutoFixButton errors={deleteNonlocalErrors} cellId={cellId} />
          )}
          <Tip title="Why can't I delete other cells' variables?">
            marimo determines how to run your notebook based on variables
            definitions and references only. When a cell deletes a variable it
            didn't define, marimo cannot determine an unambiguous execution
            order. Try refactoring so that you can delete variables in the cells
            that create them.
          </Tip>
        </li>,
      );
    }

    if (interruptionErrors.length > 0) {
      messages.push(
        <li key="interruption">
          {interruptionErrors.map((_, idx) => (
            <p key={`interruption-${idx}`}>
              {"This cell was interrupted and needs to be re-run."}
            </p>
          ))}
          {cellId && (
            <AutoFixButton errors={interruptionErrors} cellId={cellId} />
          )}
        </li>,
      );
    }

    if (exceptionErrors.length > 0) {
      messages.push(
        <li key="exception">
          {exceptionErrors.map((error, idx) => (
            <li className="my-2" key={`exception-${idx}`}>
              {error.raising_cell == null ? (
                <li>
                  <p className="text-muted-foreground">{error.msg}</p>
                  <div className="text-muted-foreground mt-2">
                    See the console area for a traceback.
                  </div>
                </li>
              ) : (
                <div>
                  {error.msg}
                  <CellLinkError cellId={error.raising_cell as CellId} />
                </div>
              )}
            </li>
          ))}
          {exceptionErrors.some((e) => e.raising_cell != null) && (
            <Tip>
              Fix the error in the mentioned cells, or handle the exceptions
              with try/except blocks.
            </Tip>
          )}
          {cellId && <AutoFixButton errors={exceptionErrors} cellId={cellId} />}
        </li>,
      );
    }

    if (strictExceptionErrors.length > 0) {
      messages.push(
        <li key="strict-exception">
          {strictExceptionErrors.map((error, idx) => (
            <li className="my-2" key={`strict-exception-${idx}`}>
              {error.blamed_cell == null ? (
                <p>{error.msg}</p>
              ) : (
                <div>
                  {error.msg}
                  <CellLinkError cellId={error.blamed_cell as CellId} />
                </div>
              )}
            </li>
          ))}
          {cellId && (
            <AutoFixButton errors={strictExceptionErrors} cellId={cellId} />
          )}
          <Tip>
            {strictExceptionErrors.some((e) => e.blamed_cell != null)
              ? "Ensure that the referenced cells define the required variables, or turn off strict execution."
              : "Something is wrong with your declarations. Fix any discrepancies, or turn off strict execution."}
          </Tip>
        </li>,
      );
    }

    if (internalErrors.length > 0) {
      messages.push(
        <li key="internal">
          {internalErrors.map((error, idx) => (
            <p key={`internal-${idx}`}>{error.msg}</p>
          ))}
          {cellId && <AutoFixButton errors={internalErrors} cellId={cellId} />}
        </li>,
      );
    }

    if (ancestorPreventedErrors.length > 0) {
      messages.push(
        <li key="ancestor-prevented">
          {ancestorPreventedErrors.map((error, idx) => (
            <div key={`ancestor-prevented-${idx}`}>
              {error.msg}
              {error.blamed_cell == null ? (
                <span>
                  (<CellLinkError cellId={error.raising_cell as CellId} />)
                </span>
              ) : (
                <span>
                  (<CellLinkError cellId={error.raising_cell as CellId} />
                  &nbsp;blames&nbsp;
                  <CellLinkError cellId={error.blamed_cell as CellId} />)
                </span>
              )}
            </div>
          ))}
          {cellId && (
            <AutoFixButton errors={ancestorPreventedErrors} cellId={cellId} />
          )}
        </li>,
      );
    }

    if (ancestorStoppedErrors.length > 0) {
      messages.push(
        <li key="ancestor-stopped">
          {ancestorStoppedErrors.map((error, idx) => (
            <div key={`ancestor-stopped-${idx}`}>
              {error.msg}
              <CellLinkError cellId={error.raising_cell as CellId} />
            </div>
          ))}
          {cellId && (
            <AutoFixButton errors={ancestorStoppedErrors} cellId={cellId} />
          )}
        </li>,
      );
    }

    return messages;
  };

  const title = (
    <AlertTitle className={`font-code font-medium tracking-wide ${titleColor}`}>
      {titleContents}
    </AlertTitle>
  );

  return (
    <Alert
      variant={alertVariant}
      className={cn(
        "border-none font-code text-sm text-[0.84375rem] px-0 text-muted-foreground normal [&:has(svg)]:pl-0 space-y-4",
        className,
      )}
    >
      {title}
      <div>
        <ul className="flex flex-col gap-8">{renderMessages()}</ul>
      </div>
    </Alert>
  );
};
