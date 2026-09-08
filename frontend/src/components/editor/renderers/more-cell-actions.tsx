/* Copyright 2026 Marimo. All rights reserved. */

import {
  BookOpenIcon,
  DatabaseIcon,
  EllipsisIcon,
  FileSpreadsheetIcon,
  ListChecksIcon,
  LineChartIcon,
  SlidersHorizontalIcon,
  SparklesIcon,
} from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import type { CellRecipe, CellRecipeId } from "./cell-recipes";
import { CELL_RECIPES } from "./cell-recipes";

interface MoreCellActionsProps {
  buttonClassName: string;
  disabled: boolean;
  onSelectRecipe: (id: CellRecipeId) => void;
  onConnectData: () => void;
  onBrowseRecipes: () => void;
  generateWithAI?: {
    description: string;
    onSelect: () => void;
  };
}

const RECIPE_ICONS = {
  "interactive-control": SlidersHorizontalIcon,
  form: ListChecksIcon,
  "read-csv-duckdb": FileSpreadsheetIcon,
  "reactive-altair-plot": LineChartIcon,
} satisfies Record<CellRecipeId, React.ComponentType<{ className?: string }>>;

interface RecipeCommandItemProps {
  recipe: CellRecipe;
  onSelect: () => void;
}

const RecipeCommandItem: React.FC<RecipeCommandItemProps> = ({
  recipe,
  onSelect,
}) => {
  const Icon = RECIPE_ICONS[recipe.id];
  return (
    <CommandItem
      value={`${recipe.title} ${recipe.description} ${recipe.keywords.join(" ")}`}
      onSelect={onSelect}
    >
      <Icon className="mr-3 size-4 shrink-0 text-muted-foreground" />
      <div className="flex flex-col">
        <span>{recipe.title}</span>
        <span className="text-xs text-muted-foreground">
          {recipe.description}
        </span>
      </div>
    </CommandItem>
  );
};

export const MoreCellActions: React.FC<MoreCellActionsProps> = ({
  buttonClassName,
  disabled,
  onSelectRecipe,
  onConnectData,
  onBrowseRecipes,
  generateWithAI,
}) => {
  const [open, setOpen] = useState(false);

  const runAction = (action: () => void) => {
    setOpen(false);
    action();
  };

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild={true}>
        <Button
          className={buttonClassName}
          variant="text"
          size="sm"
          disabled={disabled}
        >
          <EllipsisIcon className="mr-2 size-4 shrink-0" />
          More
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-96 p-0" align="start">
        <Command>
          <CommandInput placeholder="Search actions..." />
          <CommandList>
            <CommandEmpty>No actions found</CommandEmpty>
            <CommandGroup heading="Build">
              {generateWithAI && (
                <CommandItem
                  value={`Generate with AI ${generateWithAI.description}`}
                  onSelect={() => runAction(generateWithAI.onSelect)}
                >
                  <SparklesIcon className="mr-3 size-4 shrink-0 text-muted-foreground" />
                  <div className="flex flex-col">
                    <span>Generate with AI</span>
                    <span className="text-xs text-muted-foreground">
                      {generateWithAI.description}
                    </span>
                  </div>
                </CommandItem>
              )}
              {CELL_RECIPES.filter((recipe) => recipe.category === "build").map(
                (recipe) => (
                  <RecipeCommandItem
                    key={recipe.id}
                    recipe={recipe}
                    onSelect={() => runAction(() => onSelectRecipe(recipe.id))}
                  />
                ),
              )}
            </CommandGroup>
            <CommandGroup heading="Data">
              {CELL_RECIPES.filter((recipe) => recipe.category === "data").map(
                (recipe) => (
                  <RecipeCommandItem
                    key={recipe.id}
                    recipe={recipe}
                    onSelect={() => runAction(() => onSelectRecipe(recipe.id))}
                  />
                ),
              )}
              <CommandItem
                value="Connect to data database catalog storage SQL"
                onSelect={() => runAction(onConnectData)}
              >
                <DatabaseIcon className="mr-3 size-4 shrink-0 text-muted-foreground" />
                <div className="flex flex-col">
                  <span>Connect to data</span>
                  <span className="text-xs text-muted-foreground">
                    Add a database, catalog, or remote storage connection
                  </span>
                </div>
              </CommandItem>
            </CommandGroup>
            <CommandGroup heading="Examples">
              <CommandItem
                value="Browse all snippets recipes examples templates"
                onSelect={() => runAction(onBrowseRecipes)}
              >
                <BookOpenIcon className="mr-3 size-4 shrink-0 text-muted-foreground" />
                <div className="flex flex-col">
                  <span>Browse all snippets</span>
                  <span className="text-xs text-muted-foreground">
                    Explore insertable examples for common libraries
                  </span>
                </div>
              </CommandItem>
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
};
