/* Copyright 2026 Marimo. All rights reserved. */
import type { JSX, PropsWithChildren } from "react";
import React from "react";
import { z } from "zod";
import {
  NavigationMenu,
  NavigationMenuItem,
  NavigationMenuLink,
  NavigationMenuList,
  navigationMenuTriggerStyle,
} from "@/components/ui/navigation";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Tooltip } from "@/components/ui/tooltip";
import { ChevronDownIcon } from "@radix-ui/react-icons";
import { renderHTML } from "@/plugins/core/RenderHTML";
import { cn } from "@/utils/cn";
import { appendQueryParams } from "@/utils/urls";
import type {
  IStatelessPlugin,
  IStatelessPluginProps,
} from "../stateless-plugin";
import "./navigation-menu.css";
import { KnownQueryParams } from "@/core/constants";

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
  items: (MenuItem | MenuItemGroup)[];

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
    return <NavMenuComponent {...props.data} />;
  }
}

type NavMenuComponentProps = Data;

const NavMenuComponent = ({
  items,
  orientation,
}: PropsWithChildren<NavMenuComponentProps>): JSX.Element => {
  const [openMenu, setOpenMenu] = React.useState<string | null>(null);
  const timeoutRef = React.useRef<NodeJS.Timeout>(null);

  const handleMouseEnter = (label: string) => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }
    setOpenMenu(label);
  };

  const handleMouseLeave = () => {
    timeoutRef.current = setTimeout(() => {
      setOpenMenu(null);
    }, 200);
  };

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

  const preserveQueryParams = (href: string) => {
    const currentUrl = new URL(globalThis.location.href);
    return appendQueryParams({
      href,
      queryParams: currentUrl.search,
      keys: [KnownQueryParams.filePath],
    });
  };

  const renderMenuItem = (item: MenuItem | MenuItemGroup) => {
    if ("items" in item) {
      return orientation === "horizontal" ? (
        <NavigationMenuItem key={item.label}>
          <Popover
            open={openMenu === item.label}
            onOpenChange={(open) => !open && setOpenMenu(null)}
          >
            <PopoverTrigger
              asChild={true}
              onMouseEnter={() => handleMouseEnter(item.label)}
              onMouseLeave={handleMouseLeave}
            >
              <button
                className={cn(
                  navigationMenuTriggerStyle(),
                  "flex items-center",
                )}
              >
                {renderHTML({ html: item.label })}
                <ChevronDownIcon
                  className={cn(
                    "relative top-px ml-1 h-3 w-3 transition duration-300",
                    openMenu === item.label && "rotate-180",
                  )}
                  aria-hidden="true"
                />
              </button>
            </PopoverTrigger>
            <PopoverContent
              className="w-auto p-0"
              align="start"
              onMouseEnter={() => handleMouseEnter(item.label)}
              onMouseLeave={handleMouseLeave}
            >
              <ul className="grid w-[400px] gap-3 p-4 md:w-[500px] md:grid-cols-2 lg:w-[600px] ">
                {item.items.map((subItem) => (
                  <ListItem
                    key={subItem.label}
                    label={subItem.label}
                    href={preserveQueryParams(subItem.href)}
                    target={target(subItem.href)}
                  >
                    {subItem.description &&
                      renderHTML({ html: subItem.description })}
                  </ListItem>
                ))}
              </ul>
            </PopoverContent>
          </Popover>
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
                    href={preserveQueryParams(subItem.href)}
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
          href={preserveQueryParams(item.href)}
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
      <a
        ref={ref}
        className={cn(
          "block select-none space-y-1 rounded-md p-3 leading-none no-underline outline-hidden transition-colors hover:bg-accent hover:text-accent-foreground focus:bg-accent focus:text-accent-foreground",
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
    </li>
  );
});
ListItem.displayName = "ListItem";
