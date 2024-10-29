/* Copyright 2024 Marimo. All rights reserved. */
import React from "react";
import { BoxIcon, HelpCircleIcon } from "lucide-react";
import { PanelEmptyState } from "./empty-state";

import { useAsyncData } from "@/hooks/useAsyncData";
import { useUserConfig } from "@/core/config/config";
import {
  addPackage,
  getPackageList,
  removePackage,
} from "@/core/network/requests";
import { ErrorBanner } from "@/plugins/impl/common/error-banner";
import { Spinner } from "@/components/icons/spinner";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { SearchInput } from "@/components/ui/input";
import { toast } from "@/components/ui/use-toast";
import { Tooltip } from "@/components/ui/tooltip";
import { cn } from "@/utils/cn";
import { Kbd } from "@/components/ui/kbd";
import { Events } from "@/utils/events";
import { copyToClipboard } from "@/utils/copy";

export const PackagesPanel: React.FC = () => {
  const [config] = useUserConfig();
  const packageManager = config.package_management.manager;
  const { data, loading, error, reload } = useAsyncData(
    () => getPackageList(),
    [packageManager],
  );

  // Only show on the first load
  if (loading && !data) {
    return <Spinner size="medium" centered={true} />;
  }

  if (error) {
    return <ErrorBanner error={error} />;
  }

  const packages = data?.packages || [];

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      <InstallPackageForm packageManager={packageManager} onSuccess={reload} />
      <PackagesList packages={packages} onSuccess={reload} />
    </div>
  );
};

const InstallPackageForm: React.FC<{
  packageManager: string;
  onSuccess: () => void;
}> = ({ onSuccess, packageManager }) => {
  const [input, setInput] = React.useState("");
  const [loading, setLoading] = React.useState(false);

  const handleAddPackage = async () => {
    try {
      setLoading(true);
      const response = await addPackage({ package: input });
      if (response.success) {
        onSuccess();
        toast({
          title: "Package added",
          description: (
            <span>
              The package <Kbd className="inline">{input}</Kbd> and its
              dependencies has been added to your environment.
            </span>
          ),
        });
      } else {
        toast({
          title: "Failed to add package",
          description: response.error,
          variant: "danger",
        });
      }
    } finally {
      setInput("");
      setLoading(false);
    }
  };

  return (
    <div className="flex items-center w-full border-b">
      <SearchInput
        placeholder={`Install packages with ${packageManager}...`}
        icon={
          loading ? (
            <Spinner
              size="small"
              className="mr-2 h-4 w-4 shrink-0 opacity-50"
            />
          ) : (
            <BoxIcon className="mr-2 h-4 w-4 shrink-0 opacity-50" />
          )
        }
        rootClassName="flex-1 border-none"
        value={input}
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            e.preventDefault();
            handleAddPackage();
          }
        }}
        onChange={(e) => setInput(e.target.value)}
      />
      <Tooltip
        delayDuration={300}
        side="left"
        align="start"
        content={
          <div className="text-sm flex flex-col w-full max-w-[360px]">
            Packages are installed using the package manager specified in your
            user configuration. Depending on your package manager, you can
            install packages with various formats:
            <div className="flex flex-col gap-2 mt-2">
              <div>
                <span className="font-bold tracking-wide">Package name:</span> A
                package name; this will install the latest version.
                <div className="text-muted-foreground">Example: httpx</div>
              </div>
              <div>
                <span className="font-bold tracking-wide">
                  Package and version:
                </span>{" "}
                A package with a specific version or version range.
                <div className="text-muted-foreground">
                  {"Examples: httpx==0.27.0, httpx>=0.27.0"}
                </div>
              </div>
              <div>
                <span className="font-bold tracking-wide">Git:</span> A Git
                repository
                <div className="text-muted-foreground">
                  Example: git+https://github.com/encode/httpx
                </div>
              </div>
              <div>
                <span className="font-bold tracking-wide">URL:</span> A remote
                wheel or source distribution.
                <div className="text-muted-foreground">
                  Example: https://example.com/httpx-0.27.0.tar.gz
                </div>
              </div>
              <div>
                <span className="font-bold tracking-wide">Path:</span> A local
                wheel, source distribution, or project directory.
                <div className="text-muted-foreground">
                  Example: /example/foo-0.1.0-py3-none-any.whl
                </div>
              </div>
            </div>
          </div>
        }
      >
        <HelpCircleIcon
          className={
            "h-4 w-4 cursor-help text-muted-foreground hover:text-foreground bg-transparent"
          }
        />
      </Tooltip>
      <button
        type="button"
        className={cn(
          "float-right px-2 m-0 h-full text-sm text-secondary-foreground ml-2",
          input && "bg-accent text-accent-foreground",
          "disabled:cursor-not-allowed disabled:opacity-50",
        )}
        onClick={handleAddPackage}
        disabled={!input}
      >
        Add
      </button>
    </div>
  );
};

const PackagesList: React.FC<{
  onSuccess: () => void;
  packages: Array<{ name: string; version: string }>;
}> = ({ onSuccess, packages }) => {
  if (packages.length === 0) {
    return (
      <PanelEmptyState
        title="No packages"
        description="No packages are installed in this environment."
        icon={<BoxIcon />}
      />
    );
  }

  return (
    <Table className="overflow-auto flex-1">
      <TableHeader>
        <TableRow>
          <TableHead>Name</TableHead>
          <TableHead>Version</TableHead>
          <TableHead />
        </TableRow>
      </TableHeader>
      <TableBody>
        {packages.map((item) => (
          <TableRow
            key={item.name}
            className="group"
            onClick={async () => {
              await copyToClipboard(`${item.name}==${item.version}`);
              toast({
                title: "Copied to clipboard",
              });
            }}
          >
            <TableCell>{item.name}</TableCell>
            <TableCell>{item.version}</TableCell>
            <TableCell>
              <RemoveButton packageName={item.name} onSuccess={onSuccess} />
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
};

const RemoveButton: React.FC<{
  packageName: string;
  onSuccess: () => void;
}> = ({ packageName, onSuccess }) => {
  const [loading, setLoading] = React.useState(false);

  const handleRemovePackage = async () => {
    try {
      setLoading(true);
      const response = await removePackage({ package: packageName });
      if (response.success) {
        onSuccess();
        toast({
          title: "Package removed",
          description: (
            <span>
              The package <Kbd className="inline">{packageName}</Kbd> has been
              removed from your environment.
            </span>
          ),
        });
      } else {
        toast({
          title: "Failed to add package",
          description: response.error,
          variant: "danger",
        });
      }
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <Spinner
        size="small"
        className="float-right mr-2 h-4 w-4 shrink-0 opacity-50"
      />
    );
  }

  return (
    <button
      type="button"
      className={cn(
        "float-right px-2 h-full text-xs text-muted-foreground hover:text-foreground",
        "invisible group-hover:visible",
      )}
      onClick={Events.stopPropagation(handleRemovePackage)}
    >
      Remove
    </button>
  );
};
