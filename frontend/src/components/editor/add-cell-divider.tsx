/* Copyright 2024 Marimo. All rights reserved. */
import React, { useState } from "react";
import {
  PlusIcon,
  DatabaseIcon,
  SquareCodeIcon,
  SquareMIcon,
} from "lucide-react";
import { cn } from "@/utils/cn";
import { MarkdownLanguageAdapter } from "@/core/codemirror/language/markdown";
import { SQLLanguageAdapter } from "@/core/codemirror/language/sql";
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
} from "@/components/ui/dropdown-menu";

interface AddCellDividerProps {
  onAddCell: (opts: { code: string }) => void;
}

export const AddCellDivider: React.FC<AddCellDividerProps> = ({
  onAddCell,
}) => {
  const [isMenuOpen, setIsMenuOpen] = useState(false);

  const handleAddCell = (type: "python" | "markdown" | "sql") => {
    const code =
      type === "markdown"
        ? new MarkdownLanguageAdapter().defaultCode
        : type === "sql"
          ? new SQLLanguageAdapter().defaultCode
          : "";
    onAddCell({ code });
    setIsMenuOpen(false);
  };

  return (
    <div
      className={cn(
        "relative pt-2 pb-1 w-full transition-all duration-200 px-2",
        isMenuOpen ? "opacity-100" : "opacity-0 hover:opacity-100",
      )}
    >
      <DropdownMenu onOpenChange={setIsMenuOpen} open={isMenuOpen}>
        <DropdownMenuTrigger asChild={true}>
          <div className="w-full flex items-center justify-center group opacity-60 hover:opacity-100 duration-200">
            <div
              className={cn(
                "h-px w-16 flex-1 transition-all duration-200",
                isMenuOpen ? "bg-[var(--cyan-9)]" : "bg-[var(--slate-8)]",
              )}
            />
            <button
              type="button"
              className={cn(
                "rounded-full p-1 mx-1 shadow-sm transition-all duration-200",
                isMenuOpen
                  ? "bg-[var(--cyan-9)] text-[var(--slate-1)]"
                  : "bg-[var(--slate-6)] text-[var(--slate-10)]",
              )}
            >
              <PlusIcon size={8} />
            </button>
            <div
              className={cn(
                "h-px w-16 flex-1 transition-all duration-200",
                isMenuOpen ? "bg-[var(--cyan-9)]" : "bg-[var(--slate-8)]",
              )}
            />
          </div>
        </DropdownMenuTrigger>
        <DropdownMenuContent
          align="center"
          className="text-xl border shadow-lg"
        >
          {[
            { type: "python", icon: SquareCodeIcon, label: "Python" },
            { type: "markdown", icon: SquareMIcon, label: "Markdown" },
            { type: "sql", icon: DatabaseIcon, label: "SQL" },
          ].map(({ type, icon: Icon, label }) => (
            <DropdownMenuItem
              key={type}
              onSelect={() =>
                handleAddCell(type as "python" | "markdown" | "sql")
              }
              className="tracking-wide pl-3 pr-6 py-2 text-[var(--slate-11)]"
            >
              <Icon className="mr-3 size-5 flex-shrink-0" />
              <span className="font-semibold uppercase">{label}</span>
            </DropdownMenuItem>
          ))}
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
};
