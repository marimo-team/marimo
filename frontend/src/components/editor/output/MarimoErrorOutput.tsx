/* Copyright 2024 Marimo. All rights reserved. */

import { cn } from "../../../utils/cn";
import { logNever } from "../../../utils/assertNever";
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

const Tip = (props: {
  className?: string;
  children: React.ReactNode;
}): JSX.Element => {
  return (
    <Accordion type="single" collapsible={true} className={props.className}>
      <AccordionItem value="item-1" className="text-muted-foreground">
        <AccordionTrigger className="pt-4 pb-2">Tip</AccordionTrigger>
        <AccordionContent className="mr-24 text-[0.84375rem]">
          {props.children}
        </AccordionContent>
      </AccordionItem>
    </Accordion>
  );
};

const Explainer = (props: {
  title?: string;
  className?: string;
  children: React.ReactNode;
}): JSX.Element => {
  return (
    <Accordion type="single" collapsible={true} className={props.className}>
      <AccordionItem value="item-1" className="text-muted-foreground">
        <AccordionTrigger className="pt-4 pb-2">
          {props.title ?? "Learn more"}
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
  let textColor = "text-error";
  const liStyle = "my-0.5 ml-8 text-muted-foreground/40";
  const msgs = errors.map((error, idx) => {
    switch (error.type) {
      case "syntax":
      case "unknown":
        return <p key={idx}>{error.msg}</p>;

      case "cycle":
        return (
          <Fragment key={idx}>
            <p className="text-muted-foreground">
              {"This cell is in a cycle:"}
            </p>
            <ul className="list-disc">
              {error.edges_with_vars.map((edge) => (
                <li className={liStyle} key={`${edge[0]}-${edge[1]}`}>
                  <CellLinkError cellId={edge[0] as CellId} />
                  <span className="text-muted-foreground">
                    {" -> "}
                    {edge[1].length === 1 ? edge[1] : edge[1].join(", ")}
                    {" -> "}
                  </span>
                  <CellLinkError cellId={edge[2] as CellId} />
                </li>
              ))}
            </ul>
            <Tip>Merge these cells into a single cell.</Tip>
          </Fragment>
        );

      case "multiple-defs":
        return (
          <Fragment key={idx}>
            <p className="text-muted-foreground">{`The variable '${error.name}' was defined by another cell:`}</p>
            <ul className="list-disc">
              {error.cells.map((cid) => (
                <li className={liStyle} key={cid}>
                  <CellLinkError cellId={cid as CellId} />
                </li>
              ))}
            </ul>
            <Tip>
              <p className="pb-2">
                marimo requires that each variable is defined in just one cell.
                This constraint enables reactive and reproducible execution,
                arbitrary cell reordering, seamless UI elements, execution as a
                script, and more.
              </p>

              <p className="py-2">
                Try merging this cell with the above cells or wrapping it in a
                function. Alternatively, rename '{error.name}' to '_{error.name}
                ' to make the variable private to this cell.
              </p>
            </Tip>
          </Fragment>
        );

      case "import-star":
        return (
          <Fragment key={idx}>
            <p className="text-muted-foreground">{error.msg}</p>

            <Explainer>
              <p className="pb-2">
                Star imports are incompatible with marimo's git-friendly file
                format and reproducible reactive execution.
              </p>

              <p className="py-2">
                marimo's Python file format stores code in functions, so
                notebooks can be imported as regular Python modules without
                executing all their code. But Python disallows `import *`
                everywhere except at the top-level of a module.
              </p>

              <p className="py-2">
                Star imports would also silently add names to globals, which
                would be incompatible with reactive execution.
              </p>
            </Explainer>
          </Fragment>
        );

      case "delete-nonlocal":
        return (
          <Fragment key={idx}>
            <div>
              {`The variable '${error.name}' can't be deleted because it was defined by another cell (`}
              <CellLinkError cellId={error.cells[0] as CellId} />
              {")"}
            </div>
            <Tip>
              Try refactoring so that you can delete '{error.name}' in the cell
              that creates it.
            </Tip>
          </Fragment>
        );

      case "interruption":
        titleContents = "Interrupted";
        return (
          <p key={idx}>{"This cell was interrupted and needs to be re-run."}</p>
        );

      case "exception":
        titleContents = error.exception_type;
        return error.raising_cell == null ? (
          <Fragment key={idx}>
            <p className="text-muted-foreground">{error.msg}</p>
            <div className="text-muted-foreground mt-2">
              See the console area for a traceback.
            </div>
          </Fragment>
        ) : (
          <div key={idx}>
            {error.msg}
            <CellLinkError cellId={error.raising_cell as CellId} />
            <Tip>
              Fix the error in{" "}
              <CellLinkError cellId={error.raising_cell as CellId} />, or handle
              the exception in with a try/except block.
            </Tip>
          </div>
        );
      case "strict-exception":
        return error.blamed_cell == null ? (
          <Fragment key={idx}>
            <p>{error.msg}</p>
            <Tip>
              Something is wrong with your declaration of `{error.ref}`. Fix any
              discrepancies, or turn off strict execution.
            </Tip>
          </Fragment>
        ) : (
          <div key={idx}>
            {error.msg}
            <CellLinkError cellId={error.blamed_cell as CellId} />
            <Tip>
              Ensure that&nbsp;
              <CellLinkError cellId={error.blamed_cell as CellId} />
              &nbsp;defines the variable `{error.ref}`, or turn off strict
              execution.
            </Tip>
          </div>
        );
      case "internal":
        titleContents = "An internal error occurred";
        return <p key={idx}>{error.msg}</p>;

      case "ancestor-prevented":
        titleContents = "Ancestor prevented from running";
        alertVariant = "default";
        textColor = "text-secondary-foreground";
        return error.blamed_cell == null ? (
          <div key={idx}>
            {error.msg}
            (<CellLinkError cellId={error.raising_cell as CellId} />)
          </div>
        ) : (
          <div key={idx}>
            {error.msg}
            (<CellLinkError cellId={error.raising_cell as CellId} />
            &nbsp;blames&nbsp;
            <CellLinkError cellId={error.blamed_cell as CellId} />)
          </div>
        );
      case "ancestor-stopped":
        titleContents = "Ancestor stopped";
        alertVariant = "default";
        textColor = "text-secondary-foreground";
        return (
          <div key={idx}>
            {error.msg}
            <CellLinkError cellId={error.raising_cell as CellId} />
          </div>
        );

      default:
        logNever(error);
        return null;
    }
  });

  const title = (
    <AlertTitle className="font-code font-bold tracking-wide">
      {titleContents}
    </AlertTitle>
  );

  return (
    <Alert
      variant={alertVariant}
      className={cn(
        `border-none font-code text-sm text-[0.84375rem] px-0 ${textColor} normal [&:has(svg)]:pl-0 space-y-4`,
        className,
      )}
    >
      {title}
      <div>
        <ul>{msgs}</ul>
      </div>
      {cellId && <AutoFixButton errors={errors} cellId={cellId} />}
    </Alert>
  );
};
