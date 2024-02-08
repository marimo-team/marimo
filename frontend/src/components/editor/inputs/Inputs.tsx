/* Copyright 2024 Marimo. All rights reserved. */
import { VariantProps } from "class-variance-authority";
import * as styles from "./Inputs.styles";
import React from "react";
import clsx from "clsx";

type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> &
  VariantProps<typeof styles.button>;

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ color, shape, size, className, ...props }, ref) => {
    return (
      <button
        ref={ref}
        className={clsx(styles.button({ color, shape, size }), className)}
        {...props}
      >
        {props.children}
      </button>
    );
  },
);
Button.displayName = "Button";

type InputProps = React.HtmlHTMLAttributes<HTMLInputElement>;

export const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, ...props }, ref) => {
    return (
      <input ref={ref} className={clsx(styles.input(), className)} {...props} />
    );
  },
);
Input.displayName = "Input";
