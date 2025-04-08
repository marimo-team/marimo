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
import { CopyIcon } from "lucide-react";
import { Logger } from "@/utils/Logger";
import { ErrorBanner } from "../common/error-banner";
import type { ResolvedTheme } from "@/theme/useTheme";
import { Button } from "@/components/ui/button";
import { copyToClipboard } from "@/utils/copy";
import { toast } from "@/components/ui/use-toast";

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
    <div className="relative w-full  hover-actions-parent">
      {isNotSupported && (
        <ErrorBanner
          className="mb-1 rounded-sm"
          error={`Language ${language} not supported. \n\nSupported languages are: ${Object.keys(
            langs,
          ).join(", ")}`}
        />
      )}
      {showCopyButton && !isNotSupported && (
        <Button
          key="copy-button"
          data-testid="any-language-editor-copy-button"
          variant="secondary"
          size="xs"
          className="absolute top-0 right-0 z-10 hover-action"
          onClick={async () => {
            await copyToClipboard(props.value || "");
            toast({ title: "Copied to clipboard" });
          }}
        >
          <CopyIcon className="w-4 h-4 mr-1" />
          Copy code
        </Button>
      )}
      <ReactCodeMirror {...props} extensions={finalExtensions} />
    </div>
  );
};

export default AnyLanguageCodeMirror;
