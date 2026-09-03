/* Copyright 2026 Marimo. All rights reserved. */
/* oxlint-disable react/jsx-no-comment-textnodes */
/* oxlint-disable react/jsx-no-target-blank */

import { useAtomValue } from "jotai";
import { CopyIcon, DownloadIcon } from "lucide-react";
import type React from "react";
import { Constants } from "@/core/constants";
import { useResolvedMarimoConfig } from "@/core/config/config";
import { codeAtom } from "@/core/saving/file-state";
import { useFilename } from "@/core/saving/filename";
import { isStaticNotebook } from "@/core/static/static-state";
import { createShareableLink } from "@/core/wasm/share";
import { copyToClipboard } from "@/utils/copy";
import { downloadBlob } from "@/utils/download";
import { Paths } from "@/utils/paths";
import { shellQuote } from "@/utils/shell";
import { MarimoPlusIcon } from "../icons/marimo-icons";
import { Button } from "../ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "../ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../ui/tabs";
import { toast } from "../ui/use-toast";

export const StaticBanner: React.FC = () => {
  const code = useAtomValue(codeAtom);

  if (!isStaticNotebook()) {
    return null;
  }

  if (!code) {
    return null;
  }

  return (
    <div
      className="px-4 py-2 bg-(--sky-2) border-b border-(--sky-7) text-(--sky-11) flex justify-between items-center gap-4 print:hidden text-sm"
      data-testid="static-notebook-banner"
    >
      <span>
        Static{" "}
        <a
          href={Constants.githubPage}
          target="_blank"
          className="text-(--sky-11) font-medium underline"
        >
          marimo
        </a>{" "}
        notebook - Run or edit for full interactivity
      </span>
      <span className="shrink-0">
        <StaticBannerDialog code={code} />
      </span>
    </div>
  );
};

const StaticBannerDialog = ({ code }: { code: string }) => {
  const filename = Paths.basename(useFilename() || "notebook.py");

  const [resolvedConfig] = useResolvedMarimoConfig();
  const molabEnabled = resolvedConfig.sharing?.molab ?? true;

  const runTarget = getStaticNotebookRunTarget(window.location.href, filename);
  const runsFromUrl = runTarget !== filename;
  const quotedRunTarget = shellQuote(runTarget);

  return (
    <Dialog>
      <DialogTrigger asChild={true}>
        <Button
          data-testid="static-notebook-dialog-trigger"
          variant="outline"
          size="xs"
        >
          Run or Edit
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{filename}</DialogTitle>
          <DialogDescription asChild={true}>
            <div className="pt-3 text-left space-y-3">
              <p>
                This is a static{" "}
                <a
                  href={Constants.githubPage}
                  target="_blank"
                  className="text-(--sky-11) hover:underline font-medium"
                >
                  marimo
                </a>{" "}
                notebook. {runsFromUrl ? "Run it" : "Download it, then run it"}{" "}
                locally for full interactivity.
              </p>

              <Tabs defaultValue="uv">
                <TabsList aria-label="Package manager">
                  <TabsTrigger value="uv">uv</TabsTrigger>
                  <TabsTrigger value="pip">pip</TabsTrigger>
                  <TabsTrigger value="conda">conda</TabsTrigger>
                </TabsList>
                <TabsContent value="uv">
                  <CommandBlock
                    command={`uvx marimo edit --sandbox ${quotedRunTarget}`}
                  />
                </TabsContent>
                <TabsContent value="pip">
                  <CommandBlock
                    command={`pip install marimo\nmarimo edit ${quotedRunTarget}`}
                  />
                </TabsContent>
                <TabsContent value="conda">
                  <CommandBlock
                    command={`conda install -c conda-forge marimo\nmarimo edit ${quotedRunTarget}`}
                  />
                </TabsContent>
              </Tabs>

              {molabEnabled && <MolabCallout code={code} />}
            </div>
          </DialogDescription>
        </DialogHeader>
        <div className="flex gap-3 pt-2">
          <Button
            data-testid="copy-static-notebook-dialog-button"
            variant="outline"
            size="sm"
            onClick={async () => {
              await copyToClipboard(code);
              toast({ title: "Copied to clipboard" });
            }}
          >
            <CopyIcon className="w-3 h-3 mr-2" />
            Copy code
          </Button>
          <Button
            data-testid="download-static-notebook-dialog-button"
            variant="outline"
            size="sm"
            onClick={() => {
              downloadBlob(new Blob([code], { type: "text/plain" }), filename);
            }}
          >
            <DownloadIcon className="w-3 h-3 mr-2" />
            Download
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
};

/** Keep this in sync with StaticNotebookReader in marimo/_cli/files/file_path.py. */
export function getStaticNotebookRunTarget(
  href: string,
  filename: string,
): string {
  const url = new URL(href);
  const isHttp = url.protocol === "http:" || url.protocol === "https:";
  if (!isHttp) {
    return filename;
  }

  const isHtmlFile = url.pathname.endsWith(".html") && url.search === "";
  const matchesSupportedUrlPattern =
    url.protocol === "https:" &&
    (url.hostname === "marimo.app" ||
      url.hostname === "links.marimo.app" ||
      (url.hostname === "static.marimo.app" &&
        url.pathname.startsWith("/static")) ||
      url.pathname.includes("/notebooks/nb"));
  if (!isHtmlFile && !matchesSupportedUrlPattern) {
    return filename;
  }

  url.hash = "";
  return url.href;
}

const CommandBlock = ({ command }: { command: string }) => (
  <div className="relative rounded-lg border bg-(--sky-2) border-(--sky-7)">
    <pre className="p-3 pr-10 font-mono text-(--sky-11) leading-relaxed whitespace-pre-wrap break-all">
      {command}
    </pre>
    <Button
      aria-label="Copy command"
      className="absolute right-2 top-2"
      variant="ghost"
      size="icon"
      onClick={async () => {
        await copyToClipboard(command);
        toast({ title: "Command copied to clipboard" });
      }}
    >
      <CopyIcon className="w-3.5 h-3.5" />
    </Button>
  </div>
);

const MolabCallout = ({ code }: { code: string }) => {
  const molabLink = createShareableLink({
    code,
    baseUrl: `${Constants.molab}/new`,
  });

  return (
    <div className="pt-3 border-t flex gap-2 items-center">
      <Button asChild={true} variant="outline" size="xs" className="shrink-0">
        <a href={molabLink} target="_blank" rel="noopener noreferrer">
          <MarimoPlusIcon
            size={12}
            strokeWidth={1.5}
            className="mr-1.5 mt-px text-(--grass-11)"
          />
          Open in molab
        </a>
      </Button>
      <p className="text-sm text-(--sky-12)">
        Run this notebook in <span className="font-semibold">molab</span>,
        marimo's cloud-hosted notebook platform.
      </p>
    </div>
  );
};
