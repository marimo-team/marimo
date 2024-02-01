/* Copyright 2024 Marimo. All rights reserved. */
import ReactCodeMirror, { ReactCodeMirrorProps } from "@uiw/react-codemirror";
import {
  loadLanguage,
  langs,
  LanguageName,
} from "@uiw/codemirror-extensions-langs";
import React from "react";
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
    language: string;
  }
> = ({ language, extensions = [], ...props }) => {
  const isNotSupported = !(language in langs);
  if (isNotSupported) {
    Logger.warn(`Language ${language} not found in CodeMirror.`);
  }

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
      <ReactCodeMirror
        {...props}
        extensions={[
          loadLanguage(language as LanguageName),
          ...extensions,
        ].filter(Boolean)}
      />
    </>
  );
};

export default AnyLanguageCodeMirror;
