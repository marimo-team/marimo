import type { Preview, Decorator } from "@storybook/react";
import "../src/css/index.css";
import "../src/css/app/App.css";
import "./sb.css";
import "tailwindcss/tailwind.css";
import React, { useEffect } from "react";
import { cn } from "../src/utils/cn";
import { TooltipProvider } from "../src/components/ui/tooltip";
import { Toaster } from "../src/components/ui/toaster";
import { TailwindIndicator } from "../src/components/debug/indicator";

const withTheme: Decorator = (Story, context) => {
  const theme = context.globals.theme || "light";
  useEffect(() => {
    document.body.classList.add(theme, `${theme}-theme`);
    return () => document.body.classList.remove(theme, `${theme}-theme`);
  }, [theme]);

  return (
    <div className={cn(theme, "p-5")}>
      <TooltipProvider>
        <Story />
        <Toaster />
        <TailwindIndicator />
      </TooltipProvider>
    </div>
  );
};

const preview: Preview = {
  parameters: {
    actions: { argTypesRegex: "^on[A-Z].*" },
    controls: {
      matchers: {
        color: /(background|color)$/i,
        date: /Date$/,
      },
    },
  },
  globalTypes: {
    theme: {
      description: "Global theme",
      defaultValue: "light",
      toolbar: {
        title: "Theme",
        icon: "circlehollow",
        items: ["light", "dark"],
        dynamicTitle: true,
      },
    },
  },
  decorators: [withTheme],
};

export default preview;
