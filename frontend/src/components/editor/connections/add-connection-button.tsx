/* Copyright 2026 Marimo. All rights reserved. */

import {
  DatabaseIcon,
  HardDriveIcon,
  PlusIcon,
  SparklesIcon,
} from "lucide-react";
import type React from "react";
import { useImperativeModal } from "@/components/modal/ImperativeModal";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Tooltip } from "@/components/ui/tooltip";
import type { DataSourceDiscoveryGroup } from "@/core/datasets/data-source-discovery";
import { useDetectedDataSources } from "@/hooks/useDataSourceDiscovery";
import { cn } from "@/utils/cn";
import {
  AddConnectionDialog,
  AddConnectionDialogContent,
} from "./add-connection-dialog";
import { useAddDetectedDataSource } from "./components";

type AddConnectionButtonProps = Omit<
  React.ComponentProps<typeof Button>,
  "children"
> & {
  group: DataSourceDiscoveryGroup;
  label: string;
  compact?: boolean;
};

/**
 * Opens the connection dialog directly and, when useful suggestions exist,
 * adds a secondary menu for detected sources.
 */
export const AddConnectionButton: React.FC<AddConnectionButtonProps> = ({
  group,
  label,
  compact = false,
  className,
  ...buttonProps
}) => {
  const sources = useDetectedDataSources(group);
  const addDetectedDataSource = useAddDetectedDataSource();
  const { openModal, closeModal } = useImperativeModal();
  const hasSuggestions = sources.length > 0;
  const defaultTab = group === "storage" ? "storage" : "databases";

  const primaryButton = (
    <Button
      {...buttonProps}
      className={cn(className, hasSuggestions && !compact && "rounded-r-none")}
      aria-label={compact ? label : buttonProps["aria-label"]}
    >
      {!compact && label}
      <PlusIcon className={cn("h-4 w-4", !compact && "ml-2")} />
    </Button>
  );

  const primaryAction = (
    <AddConnectionDialog defaultTab={defaultTab}>
      {primaryButton}
    </AddConnectionDialog>
  );

  if (!hasSuggestions) {
    return primaryAction;
  }

  const BrowseIcon = group === "storage" ? HardDriveIcon : DatabaseIcon;
  const suggestionsLabel =
    group === "storage"
      ? "View detected remote storage connections"
      : "View detected database connections";

  return (
    <div className="inline-flex">
      {primaryAction}
      <DropdownMenu>
        <Tooltip content={suggestionsLabel}>
          <span className="inline-flex">
            <DropdownMenuTrigger asChild={true}>
              <Button
                variant={buttonProps.variant}
                size={buttonProps.size}
                disabled={buttonProps.disabled}
                className={cn(
                  "rounded-l-none border-l-0 px-2 text-(--blue-10) hover:bg-(--blue-3)",
                  compact && "rounded-none",
                )}
                aria-label={suggestionsLabel}
              >
                <SparklesIcon className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
          </span>
        </Tooltip>
        <DropdownMenuContent align="end">
          {sources.map((source) => (
            <DropdownMenuItem
              key={source.id}
              onSelect={() => addDetectedDataSource(source)}
            >
              <SparklesIcon className="mr-2 h-4 w-4 text-(--blue-9)" />
              Add {source.displayName}
            </DropdownMenuItem>
          ))}
          <DropdownMenuSeparator />
          <DropdownMenuItem
            onSelect={() =>
              openModal(
                <AddConnectionDialogContent
                  defaultTab={defaultTab}
                  onClose={closeModal}
                />,
              )
            }
          >
            <BrowseIcon className="mr-2 h-4 w-4" />
            Browse all connections
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
};
