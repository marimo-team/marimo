/* Copyright 2024 Marimo. All rights reserved. */

import { cn } from "../../../utils/cn";
import { logNever } from "../../../utils/assertNever";
import { MarimoError } from "../../../core/kernel/messages";
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

const Tip = (props: {
  className?: string;
  children: React.ReactNode;
}): JSX.Element => {
  return (
    <Accordion type="single" collapsible={true} className={props.className}>
      <AccordionItem
        value="item-1"
        className="text-muted-foreground border-muted-foreground-20"
      >
        <AccordionTrigger className="py-2 text-[0.84375rem]">
          Tip:
        </AccordionTrigger>
        <AccordionContent className="text-[0.84375rem]">
          {props.children}
        </AccordionContent>
      </AccordionItem>
    </Accordion>
  );
};

interface Props {
  errors: MarimoError[];
  className?: string;
}

/**
 * List of errors due to violations of Marimo semantics.
 */
export const MarimoErrorOutput = ({
  errors,
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
            <p className="mt-4">{"This cell is in a cycle:"}</p>
            <ul className="list-disc">
              {error.edges.map((edge) => (
                <li className={liStyle} key={`${edge[0]}-${edge[1]}`}>
                  <CellLinkError cellId={edge[0]} />
                  {" -> "}
                  <CellLinkError cellId={edge[1]} />
                </li>
              ))}
            </ul>
            <Tip>Merge these cells into a single cell.</Tip>
          </Fragment>
        );

      case "multiple-defs":
        return (
          <Fragment key={idx}>
            <p className="mt-4">
              {`The variable '${error.name}' was defined by another cell:`}
            </p>
            <ul className="list-disc">
              {error.cells.map((cid) => (
                <li className={liStyle} key={cid}>
                  <CellLinkError cellId={cid} />
                </li>
              ))}
            </ul>
            <Tip>
              Try merging this cell with the above cells. Alternatively, rename
              '{error.name}' to '_{error.name}' to make the variable private to
              this cell.
            </Tip>
          </Fragment>
        );

      case "delete-nonlocal":
        return (
          <Fragment key={idx}>
            <div className="mt-4">
              {`The variable '${error.name}' can't be deleted because it was defined by another cell ` +
                `(`}
              <CellLinkError cellId={error.cells[0]} />
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
            <p>{error.msg}</p>
            <Tip>See the console area for a traceback.</Tip>
          </Fragment>
        ) : (
          <div key={idx}>
            {error.msg}
            <CellLinkError cellId={error.raising_cell} />
            <Tip>
              Fix the error in <CellLinkError cellId={error.raising_cell} />, or
              handle the exception in with a try/except block.
            </Tip>
          </div>
        );
      case "ancestor-stopped":
        titleContents = "Ancestor stopped";
        alertVariant = "default";
        textColor = "text-secondary-foreground";
        return (
          <div key={idx}>
            {error.msg}
            <CellLinkError cellId={error.raising_cell} />
          </div>
        );

      default:
        logNever(error);
        return null;
    }
  });

  const title = (
    <AlertTitle className="font-code font-bold mb-4">
      {titleContents}
    </AlertTitle>
  );

  return (
    <Alert
      variant={alertVariant}
      className={cn(
        `border-none font-code text-sm text-[0.84375rem] px-0 ${textColor} normal [&:has(svg)]:pl-0`,
        className,
      )}
    >
      {title}
      <div>
        <ul>{msgs}</ul>
      </div>
    </Alert>
  );
};
