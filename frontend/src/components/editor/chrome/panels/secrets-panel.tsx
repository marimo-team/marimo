/* Copyright 2026 Marimo. All rights reserved. */

import { CheckIcon, CopyIcon, KeyIcon, PlusIcon } from "lucide-react";
import React from "react";
import { Panel, PanelGroup, PanelResizeHandle } from "react-resizable-panels";
import { Spinner } from "@/components/icons/spinner";
import { useImperativeModal } from "@/components/modal/ImperativeModal";
import { Badge } from "@/components/ui/badge";
import { SearchInput } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { toast } from "@/components/ui/use-toast";
import { SECRETS_REGISTRY } from "@/core/secrets/request-registry";
import { useAsyncData } from "@/hooks/useAsyncData";
import { ErrorBanner } from "@/plugins/impl/common/error-banner";
import { cn } from "@/utils/cn";
import { copyToClipboard } from "@/utils/copy";
import { PanelEmptyState } from "./empty-state";
import { filterSecretKeys } from "./secrets-utils";
import { sortProviders, WriteSecretModal } from "./write-secret-modal";

const SecretsPanel: React.FC = () => {
  const { openModal, closeModal } = useImperativeModal();
  const [search, setSearch] = React.useState("");
  const {
    data: secretKeyProviders,
    isPending,
    error,
    refetch,
  } = useAsyncData(async () => {
    const result = await SECRETS_REGISTRY.request({});
    return sortProviders(result.secrets);
  }, []);

  // Only show on the first load
  if (isPending) {
    return <Spinner size="medium" centered={true} />;
  }

  if (error) {
    return <ErrorBanner error={error} />;
  }

  // Provider names without 'env' provider
  const providerNames = secretKeyProviders
    .filter((provider) => provider.provider !== "env")
    .map((provider) => provider.name);

  if (secretKeyProviders.length === 0) {
    return (
      <PanelEmptyState
        title="No environment variables"
        description="No environment variables are available in this notebook."
        icon={<KeyIcon />}
      />
    );
  }

  const filteredProviders = filterSecretKeys(secretKeyProviders, search);

  return (
    <PanelGroup direction="horizontal" className="h-full">
      <Panel defaultSize={50} minSize={30} maxSize={80}>
        <div className="flex flex-col h-full">
          <div className="flex items-center h-8 border-b">
            <SearchInput
              placeholder="Search environment variables..."
              aria-label="Search environment variables"
              className="h-6 min-w-0"
              rootClassName="flex-1 min-w-0 h-full border-b-0 border-r"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
            <button
              type="button"
              aria-label="Add environment variable"
              className="shrink-0 px-2 m-0 h-full hover:bg-accent hover:text-accent-foreground"
              onClick={() =>
                openModal(
                  <WriteSecretModal
                    providerNames={providerNames}
                    onSuccess={() => {
                      refetch();
                      closeModal();
                    }}
                    onClose={closeModal}
                  />,
                )
              }
            >
              <PlusIcon className="h-4 w-4" />
            </button>
          </div>
          <Table className="table-fixed overflow-auto flex-1 mb-16">
            <TableHeader>
              <TableRow>
                <TableHead>Environment Variable</TableHead>
                <TableHead className="w-1/4">Source</TableHead>
                <TableHead className="w-10" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredProviders.length === 0 && (
                <TableRow>
                  <TableCell
                    colSpan={3}
                    className="text-center text-muted-foreground"
                  >
                    No results
                  </TableCell>
                </TableRow>
              )}
              {filteredProviders.map((provider) => {
                return provider.keys.map((key) => (
                  <TableRow key={`${provider.name}-${key}`} className="group">
                    <TableCell className="break-all">{key}</TableCell>
                    <TableCell>
                      {provider.provider !== "env" && (
                        <Badge
                          variant="outline"
                          className="select-none max-w-full"
                          title={provider.name}
                        >
                          <span className="truncate">{provider.name}</span>
                        </Badge>
                      )}
                    </TableCell>
                    <TableCell>
                      <CopyButton
                        ariaLabel={`Copy ${key}`}
                        onCopy={async () => {
                          await copyToClipboard(`os.environ["${key}"]`);
                          toast({
                            title: "Copied to clipboard",
                            description: `os.environ["${key}"] has been copied to your clipboard.`,
                          });
                        }}
                        className={cn(
                          "float-right px-2 h-full text-xs text-muted-foreground hover:text-foreground",
                          "invisible group-hover:visible",
                        )}
                      />
                    </TableCell>
                  </TableRow>
                ));
              })}
            </TableBody>
          </Table>
        </div>
      </Panel>
      <PanelResizeHandle className="w-1 bg-border hover:bg-primary/50 transition-colors" />
      <Panel defaultSize={50}>
        <div />
      </Panel>
    </PanelGroup>
  );
};

export default SecretsPanel;

const CopyButton: React.FC<{
  className?: string;
  ariaLabel: string;
  onCopy: () => void;
}> = ({ className, ariaLabel, onCopy }) => {
  const [copied, setCopied] = React.useState(false);

  const handleCopy = () => {
    onCopy();
    setCopied(true);
    setTimeout(() => setCopied(false), 1000);
  };

  return (
    <button
      type="button"
      className={className}
      onClick={handleCopy}
      aria-label={ariaLabel}
    >
      {copied ? (
        <CheckIcon className="w-3 h-3 text-green-700 rounded" />
      ) : (
        <CopyIcon className="w-3 h-3 hover:bg-muted rounded" />
      )}
    </button>
  );
};
