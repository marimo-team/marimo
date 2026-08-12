/* Copyright 2026 Marimo. All rights reserved. */
import type { JSX, PropsWithChildren } from "react";
import React from "react";
import { createPortal } from "react-dom";
import { z } from "zod";
import { withFullScreenAsRoot } from "@/components/ui/fullscreen";
import {
  NavigationMenu,
  NavigationMenuContent,
  NavigationMenuItem,
  NavigationMenuLink,
  NavigationMenuList,
  NavigationMenuTrigger,
  NavigationMenuViewport,
  navigationMenuTriggerStyle,
} from "@/components/ui/navigation";
import { Tooltip } from "@/components/ui/tooltip";
import { useResizeObserver } from "@/hooks/useResizeObserver";
import { renderHTML } from "@/plugins/core/RenderHTML";
import { cn } from "@/utils/cn";
import { appendQueryParams } from "@/utils/urls";
import type {
  IStatelessPlugin,
  IStatelessPluginProps,
} from "../stateless-plugin";
import "./navigation-menu.css";
import { KnownQueryParams } from "@/core/constants";
import { NavigationMenu as NavigationMenuPrimitive } from "radix-ui";

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

interface PortalPosition {
  left: number;
  top: number;
}

interface HorizontalMenuGroupProps {
  item: MenuItemGroup;
  preserveQueryParams: (href: string) => string;
  target: (href: string) => string;
}

const HorizontalMenuGroup = ({
  item,
  preserveQueryParams,
  target,
}: HorizontalMenuGroupProps): JSX.Element => {
  const triggerRef = React.useRef<React.ComponentRef<
    typeof NavigationMenuTrigger
  > | null>(null);
  const [open, setOpen] = React.useState(false);

  return (
    <NavigationMenuPrimitive.Root
      className="relative z-10 max-w-max flex-1 items-center justify-center"
      orientation="horizontal"
      onValueChange={(value) => setOpen(value !== "")}
    >
      <NavigationMenuList>
        <NavigationMenuItem>
          <NavigationMenuTrigger ref={triggerRef}>
            {renderHTML({ html: item.label })}
          </NavigationMenuTrigger>
          <NavigationMenuContent className="w-auto">
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
          </NavigationMenuContent>
        </NavigationMenuItem>
      </NavigationMenuList>
      <NavigationMenuViewportPortal anchorRef={triggerRef} open={open}>
        <NavigationMenuViewport />
      </NavigationMenuViewportPortal>
    </NavigationMenuPrimitive.Root>
  );
};

// Portal into the fullscreen element (or VSCode output container) when
// present; `position: fixed` elements portaled to document.body render
// behind a fullscreened cell.
const NavigationMenuPortal = withFullScreenAsRoot(
  ({
    container,
    children,
  }: PropsWithChildren<{
    container?: Element | DocumentFragment | null;
  }>) => createPortal(children, container ?? document.body),
);

const VIEWPORT_MARGIN = 8;

const NavigationMenuViewportPortal = ({
  anchorRef,
  open,
  children,
}: PropsWithChildren<{
  anchorRef: React.RefObject<HTMLElement | null>;
  open: boolean;
}>): React.ReactElement | null => {
  const [position, setPosition] = React.useState<PortalPosition | null>(null);
  const contentRef = React.useRef<HTMLDivElement | null>(null);

  const updatePosition = React.useCallback(() => {
    if (!anchorRef.current) {
      return;
    }

    const rect = anchorRef.current.getBoundingClientRect();
    // Clamp so a wide dropdown doesn't run off the right edge of the viewport.
    const contentWidth =
      contentRef.current?.firstElementChild?.scrollWidth ?? 0;
    const maxLeft = window.innerWidth - contentWidth - VIEWPORT_MARGIN;
    setPosition({
      left: Math.max(VIEWPORT_MARGIN, Math.min(rect.left, maxLeft)),
      top: rect.bottom,
    });
  }, [anchorRef]);

  // Recompute whenever the menu opens: the trigger may have moved since mount
  // due to layout shifts that emit no scroll/resize events. The rAF re-measures
  // after the dropdown content has rendered, so clamping sees its real width.
  React.useLayoutEffect(() => {
    updatePosition();
    if (open) {
      const raf = requestAnimationFrame(updatePosition);
      return () => cancelAnimationFrame(raf);
    }
  }, [open, updatePosition]);

  useResizeObserver({
    ref: anchorRef,
    onResize: updatePosition,
  });

  React.useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    window.addEventListener("resize", updatePosition);
    document.addEventListener("scroll", updatePosition, { capture: true });

    return () => {
      window.removeEventListener("resize", updatePosition);
      document.removeEventListener("scroll", updatePosition, { capture: true });
    };
  }, [updatePosition]);

  if (!position || typeof document === "undefined") {
    return null;
  }

  return (
    <NavigationMenuPortal>
      <div
        ref={contentRef}
        className="fixed z-50"
        style={{ left: position.left, top: position.top }}
      >
        {children}
      </div>
    </NavigationMenuPortal>
  );
};

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
        <HorizontalMenuGroup
          key={item.label}
          item={item}
          preserveQueryParams={preserveQueryParams}
          target={target}
        />
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
  React.ComponentRef<"a">,
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
      </NavigationMenuLink>
    </li>
  );
});
ListItem.displayName = "ListItem";
