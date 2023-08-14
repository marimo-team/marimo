/* Copyright 2023 Marimo. All rights reserved. */
import { useTheme } from "../../theme/useTheme";
import { Checkbox } from "../ui/checkbox";
import { FormItem, FormLabel, FormControl } from "../ui/form";

export const ThemeToggle: React.FC = () => {
  const { theme, setTheme } = useTheme();

  if (process.env.NODE_ENV === "production") {
    return null;
  }

  return (
    <FormItem className="flex flex-row items-start space-x-2 space-y-0 pt-2">
      <FormControl>
        <Checkbox
          checked={theme === "dark"}
          onCheckedChange={(checked) => {
            return setTheme(checked === true ? "dark" : "light");
          }}
        />
      </FormControl>
      <FormLabel className="font-normal">Dark mode</FormLabel>
    </FormItem>
  );
};
