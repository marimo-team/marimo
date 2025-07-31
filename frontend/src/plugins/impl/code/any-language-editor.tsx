/* Copyright 2024 Marimo. All rights reserved. */

import {
  type LanguageName,
  langs,
  loadLanguage,
} from "@uiw/codemirror-extensions-langs";
import ReactCodeMirror, {
  type Extension,
  type ReactCodeMirrorProps,
} from "@uiw/react-codemirror";
import React, { useMemo } from "react";
import { CopyClipboardIcon } from "@/components/icons/copy-icon";
import type { ResolvedTheme } from "@/theme/useTheme";
import { Logger } from "@/utils/Logger";
import { ErrorBanner } from "../common/error-banner";

/**
 * A code editor that supports any language.
 *
 * This lives in a separate file because we want to lazy load the additional
 * language support.
 */
const AnyLanguageCodeMirror: React.FC<
  ReactCodeMirrorProps & {
    language: string | undefined;
    theme: ResolvedTheme;
    showCopyButton?: boolean;
  }
> = ({ language, showCopyButton, extensions = [], ...props }) => {
  const isNotSupported = language && !(language in langs);
  if (isNotSupported) {
    Logger.warn(`Language ${language} not found in CodeMirror.`);
  }

  const finalExtensions = useMemo((): Extension[] => {
    if (!language) {
      return extensions;
    }
    return [loadLanguage(language as LanguageName), ...extensions].filter(
      Boolean,
    );
  }, [language, extensions]);

  return (
    <div className="relative w-full group hover-actions-parent">
      {isNotSupported && (
        <ErrorBanner
          className="mb-1 rounded-sm"
          error={`Language ${language} not supported. \n\nSupported languages are: ${Object.keys(
            langs,
          ).join(", ")}`}
        />
      )}
      {showCopyButton && !isNotSupported && (
        <CopyClipboardIcon
          tooltip={false}
          className="absolute top-2 right-2 p-1 hover-action z-10 text-muted-foreground"
          value={props.value || ""}
          toastTitle="Copied to clipboard"
        />
      )}
      <ReactCodeMirror {...props} extensions={finalExtensions} />
    </div>
  );
};

export default AnyLanguageCodeMirror;
