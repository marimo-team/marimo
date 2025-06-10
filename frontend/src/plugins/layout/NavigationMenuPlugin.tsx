/* Copyright 2024 Marimo. All rights reserved. */
import type { PropsWithChildren, JSX } from "react";

import { z } from "zod";
import type {
  IStatelessPlugin,
  IStatelessPluginProps,
} from "../stateless-plugin";
import {
  NavigationMenu,
  NavigationMenuList,
  NavigationMenuItem,
  NavigationMenuTrigger,
  NavigationMenuContent,
  NavigationMenuLink,
  navigationMenuTriggerStyle,
} from "@/components/ui/navigation";
import { cn } from "@/utils/cn";
import React from "react";
import { renderHTML } from "@/plugins/core/RenderHTML";
import { Tooltip, TooltipProvider } from "@/components/ui/tooltip";
import "./navigation-menu.css";

interface MenuItem {
  label: string;
  href: string;
  description?: string | null;
}

interface MenuItemGroup {
  label: string;
  items: MenuItem[];
}

interface Data {
  /**
   * The labels for each item; raw HTML.
   */
  items: Array<MenuItem | MenuItemGroup>;

  /**
   * The orientation of the menu.
   */
  orientation: "horizontal" | "vertical";
}

export class NavigationMenuPlugin implements IStatelessPlugin<Data> {
  tagName = "marimo-nav-menu";

  private menuItemValidator = z.object({
    label: z.string(),
    href: z.string(),
    description: z.string().nullish(),
  });

  private menuItemGroupValidator = z.object({
    label: z.string(),
    items: z.array(this.menuItemValidator),
  });

  validator = z.object({
    items: z.array(
      z.union([this.menuItemValidator, this.menuItemGroupValidator]),
    ),
    orientation: z.enum(["horizontal", "vertical"]),
  });

  render(props: IStatelessPluginProps<Data>): JSX.Element {
    return (
      <TooltipProvider>
        <NavMenuComponent {...props.data} />
      </TooltipProvider>
    );
  }
}

type NavMenuComponentProps = Data;

const NavMenuComponent = ({
  items,
  orientation,
}: PropsWithChildren<NavMenuComponentProps>): JSX.Element => {
  const maybeWithTooltip = (
    component: JSX.Element,
    description?: string | null,
  ) => {
    return description ? (
      <Tooltip delayDuration={200} content={renderHTML({ html: description })}>
        {component}
      </Tooltip>
    ) : (
      component
    );
  };

  const target = (href: string) => {
    if (href.startsWith("http")) {
      return "_blank";
    }
    return "_self";
  };

  const renderMenuItem = (item: MenuItem | MenuItemGroup) => {
    if ("items" in item) {
      return orientation === "horizontal" ? (
        <NavigationMenuItem key={item.label}>
          <NavigationMenuTrigger>
            {renderHTML({ html: item.label })}
          </NavigationMenuTrigger>
          <NavigationMenuContent>
            <NavigationMenuList>
              <ul className="grid w-[400px] gap-3 p-4 md:w-[500px] md:grid-cols-2 lg:w-[600px] ">
                {item.items.map((subItem) => (
                  <ListItem
                    key={subItem.label}
                    label={subItem.label}
                    href={subItem.href}
                    target={target(subItem.href)}
                  >
                    {subItem.description &&
                      renderHTML({ html: subItem.description })}
                  </ListItem>
                ))}
              </ul>
            </NavigationMenuList>
          </NavigationMenuContent>
        </NavigationMenuItem>
      ) : (
        <NavigationMenuItem key={item.label}>
          <div
            className={
              "inline-flex h-9 w-max items-center justify-center rounded-md px-4 py-2 text-base font-medium text-muted-foreground/80 tracking-wide font-semibold"
            }
          >
            {renderHTML({ html: item.label })}
          </div>
          <NavigationMenuList
            className="ml-4 auto-collapse-nav"
            orientation={orientation}
          >
            {item.items.map((subItem) => (
              <React.Fragment key={subItem.label}>
                {maybeWithTooltip(
                  <NavigationMenuLink
                    key={subItem.label}
                    href={subItem.href}
                    target={target(subItem.href)}
                    className={navigationMenuTriggerStyle({
                      orientation: orientation,
                    })}
                  >
                    {renderHTML({ html: subItem.label })}
                  </NavigationMenuLink>,
                  subItem.description,
                )}
              </React.Fragment>
            ))}
          </NavigationMenuList>
        </NavigationMenuItem>
      );
    }

    return (
      <NavigationMenuItem key={item.label}>
        <NavigationMenuLink
          href={item.href}
          target={target(item.href)}
          className={navigationMenuTriggerStyle({
            orientation: orientation,
          })}
        >
          {renderHTML({ html: item.label })}
        </NavigationMenuLink>
      </NavigationMenuItem>
    );
  };

  return (
    <NavigationMenu orientation={orientation}>
      <NavigationMenuList
        className="auto-collapse-nav"
        orientation={orientation}
      >
        {items.map((item) => renderMenuItem(item))}
      </NavigationMenuList>
    </NavigationMenu>
  );
};

const ListItem = React.forwardRef<
  React.ElementRef<"a">,
  React.ComponentPropsWithoutRef<"a"> & {
    label: string;
  }
>(({ className, label, children, ...props }, ref) => {
  return (
    <li>
      <NavigationMenuLink asChild={true}>
        <a
          ref={ref}
          className={cn(
            "block select-none space-y-1 rounded-md p-3 leading-none no-underline outline-none transition-colors hover:bg-accent hover:text-accent-foreground focus:bg-accent focus:text-accent-foreground",
            className,
          )}
          {...props}
        >
          <div className="text-base font-medium leading-none">
            {renderHTML({ html: label })}
          </div>
          {children && (
            <p className="line-clamp-2 text-sm leading-snug text-muted-foreground">
              {children}
            </p>
          )}
        </a>
      </NavigationMenuLink>
    </li>
  );
});
ListItem.displayName = "ListItem";
