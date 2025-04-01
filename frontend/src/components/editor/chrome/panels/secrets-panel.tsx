/* Copyright 2024 Marimo. All rights reserved. */
import React from "react";
import { KeyIcon } from "lucide-react";
import { useAsyncData } from "@/hooks/useAsyncData";
import { Spinner } from "@/components/icons/spinner";
import { ErrorBanner } from "@/plugins/impl/common/error-banner";
import { PanelEmptyState } from "./empty-state";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { toast } from "@/components/ui/use-toast";
import { copyToClipboard } from "@/utils/copy";
import { cn } from "@/utils/cn";
import { SECRETS_REGISTRY } from "@/core/secrets/request-registry";
import { Badge } from "@/components/ui/badge";
import type { ListSecretKeysResponse } from "@/core/network/types";

// dotenv providers should be at the top
function sortProviders(providers: ListSecretKeysResponse["keys"]) {
  return providers.sort((a, b) => {
    if (a.provider === "env") {
      return 1;
    }
    if (b.provider === "env") {
      return -1;
    }
    return 0;
  });
}

export const SecretsPanel: React.FC = () => {
  const {
    data: secretKeyProviders = [],
    loading,
    error,
  } = useAsyncData(async () => {
    const result = await SECRETS_REGISTRY.request({});
    return sortProviders(result.secrets);
  }, []);

  // Only show on the first load
  if (loading && secretKeyProviders.length === 0) {
    return <Spinner size="medium" centered={true} />;
  }

  if (error) {
    return <ErrorBanner error={error} />;
  }

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
    <Table className="overflow-auto flex-1">
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
                <button
                  type="button"
                  onClick={async () => {
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
                >
                  Copy
                </button>
              </TableCell>
            </TableRow>
          ));
        })}
      </TableBody>
    </Table>
  );
};
