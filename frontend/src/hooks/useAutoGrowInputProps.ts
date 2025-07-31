/* Copyright 2024 Marimo. All rights reserved. */
import type React from "react";
import { useRef, useState } from "react";
import { useOnMount } from "./useLifecycle";

export function useAutoGrowInputProps(opts: {
  minWidth?: number;
  padding?: number;
}) {
  const { minWidth = 70, padding = 15 } = opts;
  const [inputWidth, setInputWidth] = useState(50);
  const inputRef = useRef<HTMLInputElement>(null);
  const spanRef = useRef<HTMLSpanElement>(null);

  const adjustWidth = (value: string) => {
    if (spanRef.current && inputRef.current) {
      const tmp = spanRef.current;
      tmp.style.fontSize = window.getComputedStyle(inputRef.current).fontSize;
      tmp.style.fontFamily = window.getComputedStyle(
        inputRef.current,
      ).fontFamily;
      tmp.textContent = value;
      const width = tmp.offsetWidth;
      setInputWidth(width + padding);
    }
  };

  // Run on mount
  useOnMount(() => {
    adjustWidth(inputRef.current?.value ?? "");
  });

  const inputProps: React.InputHTMLAttributes<HTMLInputElement> & {
    ref: React.RefObject<HTMLInputElement | null>;
  } = {
    ref: inputRef,
    type: "text",
    onChange: (e) => {
      adjustWidth(e.target.value);
    },
    style: { width: `${inputWidth}px`, minWidth: `${minWidth}px` },
  };

  const spanProps: React.HTMLAttributes<HTMLSpanElement> & {
    ref: React.RefObject<HTMLSpanElement | null>;
  } = {
    ref: spanRef,
    style: {
      visibility: "hidden",
      position: "absolute",
      whiteSpace: "pre",
    },
  };

  return { inputProps, spanProps };
}
