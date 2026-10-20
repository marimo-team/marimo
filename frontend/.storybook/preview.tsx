import type { Decorator, Preview } from "@storybook/react-vite";
import "../src/css/index.css";
import "../src/css/app/App.css";
import "./sb.css";
import "tailwindcss";
import React, { useEffect } from "react";
import { TailwindIndicator } from "../src/components/debug/indicator";
import { Toaster } from "../src/components/ui/toaster";
import { TooltipProvider } from "../src/components/ui/tooltip";
import { cn } from "../src/utils/cn";

const ThemeProvider = ({
  theme,
  children,
}: {
  theme: string;
  children: React.ReactNode;
}) => {
  useEffect(() => {
    document.body.classList.add(theme, `${theme}-theme`);
    return () => document.body.classList.remove(theme, `${theme}-theme`);
  }, [theme]);

  return (
    <div className={cn(theme, "p-5")}>
      <TooltipProvider>
        {children}
        <Toaster />
        <TailwindIndicator />
      </TooltipProvider>
    </div>
  );
};

const withTheme: Decorator = (Story, context) => (
  <ThemeProvider theme={context.globals.theme || "light"}>
    <Story />
  </ThemeProvider>
);

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
