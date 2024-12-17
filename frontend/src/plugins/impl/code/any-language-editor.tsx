/* Copyright 2024 Marimo. All rights reserved. */
import ReactCodeMirror, {
  type Extension,
  type ReactCodeMirrorProps,
} from "@uiw/react-codemirror";
import {
  loadLanguage,
  langs,
  type LanguageName,
} from "@uiw/codemirror-extensions-langs";
import React, { useMemo } from "react";
import { Logger } from "@/utils/Logger";
import { ErrorBanner } from "../common/error-banner";
import type { ResolvedTheme } from "@/theme/useTheme";

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
  }
> = ({ language, extensions = [], ...props }) => {
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
    <>
      {isNotSupported && (
        <ErrorBanner
          className="mb-1 rounded-sm"
          error={`Language ${language} not supported. \n\nSupported languages are: ${Object.keys(
            langs,
          ).join(", ")}`}
        />
      )}
      <ReactCodeMirror {...props} extensions={finalExtensions} />
    </>
  );
};

export default AnyLanguageCodeMirror;
