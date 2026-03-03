/* Copyright 2026 Marimo. All rights reserved. */

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

export const LANGUAGE_MAP: Record<string, LanguageName | undefined> = {
  python: "py",
  python3: "py",
  javascript: "js",
  typescript: "ts",
  shell: "sh",
  bash: "sh",
  // Other fallbacks
  unknown: "text",
  undefined: "text",
};

function isSupportedLanguage(
  language: string | undefined,
): language is LanguageName {
  if (!language) {
    return false;
  }
  return language in langs;
}

/**
 * A code editor that supports any language.
 *
 * This lives in a separate file because we want to lazy load the additional
 * language support.
 */
const AnyLanguageCodeMirror: React.FC<
  ReactCodeMirrorProps & {
    language: string | undefined;
    hideUnsupportedLanguageErrors?: boolean;
    theme: ResolvedTheme;
    showCopyButton?: boolean;
  }
> = ({
  language,
  hideUnsupportedLanguageErrors,
  showCopyButton,
  extensions = [],
  ...props
}) => {
  // Maybe normalize the language to the extension
  language = LANGUAGE_MAP[language || ""] || language;

  const isSupported = isSupportedLanguage(language);
  if (!isSupported) {
    Logger.warn(`Language ${language} not found in CodeMirror.`);
  }

  const finalExtensions = useMemo((): Extension[] => {
    if (!isSupportedLanguage(language)) {
      return extensions;
    }
    return [loadLanguage(language), ...extensions].filter(Boolean);
  }, [language, extensions]);

  return (
    <div className="relative w-full group hover-actions-parent">
      {!isSupported && !hideUnsupportedLanguageErrors && (
        <ErrorBanner
          className="mb-1 rounded-sm"
          error={`Language ${language} not supported. Supported languages are: ${Object.keys(
            langs,
          ).join(", ")}`}
        />
      )}
      {showCopyButton && isSupported && (
        <CopyClipboardIcon
          tooltip={false}
          buttonClassName="absolute top-2 right-2 z-10 hover-action"
          className="h-4 w-4 text-muted-foreground"
          value={props.value || ""}
          toastTitle="Copied to clipboard"
        />
      )}
      <ReactCodeMirror {...props} extensions={finalExtensions} />
    </div>
  );
};

export default AnyLanguageCodeMirror;
