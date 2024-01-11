/* Copyright 2023 Marimo. All rights reserved. */
import ReactCodeMirror, { ReactCodeMirrorProps } from "@uiw/react-codemirror";
import {
  loadLanguage,
  langs,
  LanguageName,
} from "@uiw/codemirror-extensions-langs";
import React from "react";
import { Logger } from "@/utils/Logger";

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
  if (!(language in langs)) {
    Logger.warn(`Language ${language} not found in CodeMirror.`);
  }

  return (
    <ReactCodeMirror
      {...props}
      extensions={[
        loadLanguage(language as LanguageName),
        ...extensions,
      ].filter(Boolean)}
    />
  );
};

export default AnyLanguageCodeMirror;
