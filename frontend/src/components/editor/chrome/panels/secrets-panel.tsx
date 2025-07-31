/* Copyright 2024 Marimo. All rights reserved. */

import { CheckIcon, CopyIcon, KeyIcon, PlusIcon } from "lucide-react";
import React from "react";
import { Spinner } from "@/components/icons/spinner";
import { useImperativeModal } from "@/components/modal/ImperativeModal";
import { Badge } from "@/components/ui/badge";
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
import { sortProviders, WriteSecretModal } from "./write-secret-modal";

export const SecretsPanel: React.FC = () => {
  const { openModal, closeModal } = useImperativeModal();
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

  return (
    <div className="flex flex-col h-full">
      <div className="flex justify-end h-8 border-b">
        <button
          type="button"
          className="float-right border-l px-2 m-0 h-full hover:bg-accent hover:text-accent-foreground"
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
      <Table className="overflow-auto flex-1 mb-16">
        <TableHeader>
          <TableRow>
            <TableHead>Environment Variable</TableHead>
            <TableHead>Source</TableHead>
            <TableHead />
          </TableRow>
        </TableHeader>
        <TableBody>
          {secretKeyProviders.map((provider) => {
            return provider.keys.map((key) => (
              <TableRow key={`${provider.name}-${key}`} className="group">
                <TableCell>{key}</TableCell>
                <TableCell>
                  {provider.provider !== "env" && (
                    <Badge variant="outline" className="select-none">
                      {provider.name}
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
  );
};

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
