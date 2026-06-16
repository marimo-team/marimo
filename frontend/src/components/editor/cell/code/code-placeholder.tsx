import "./code-placeholder.css";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/utils/cn";

interface CodePlaceholderProps {
  code: string;
  className?: string;
}

// Bound the rendered bars so a very long cell does not create excessive nodes.
const MAX_LINES = 50;
const MIN_LINE_WIDTH_CH = 4;
const MAX_LINE_WIDTH_CH = 60;

function getLineWidthCh(length: number): number {
  return Math.min(MAX_LINE_WIDTH_CH, Math.max(MIN_LINE_WIDTH_CH, length));
}

/**
 * Stand-in shown while a cell's CodeMirror editor has not been built yet.
 * one skeleton bar per code line, so the final render doesn't cause a big jump.
 */
export const CodePlaceholder = ({ code, className }: CodePlaceholderProps) => {
  const lines = code.split("\n").slice(0, MAX_LINES);
  return (
    <div
      className={cn("cm", "mo-code-placeholder", className)}
      data-testid="cell-editor-placeholder"
      aria-hidden={true}
    >
      {lines.map((line, index) => {
        const length = line.trimEnd().length;
        return (
          <div key={index} className="mo-code-placeholder-line">
            {length > 0 && (
              <Skeleton
                className="mo-code-placeholder-bar"
                style={{ width: `${getLineWidthCh(length)}ch` }}
              />
            )}
          </div>
        );
      })}
    </div>
  );
};
