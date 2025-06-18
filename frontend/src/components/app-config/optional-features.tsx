/* Copyright 2024 Marimo. All rights reserved. */

import { useQuery } from "@tanstack/react-query";
import { BoxIcon, CheckCircleIcon, XCircleIcon } from "lucide-react";
import React from "react";
import { Spinner } from "@/components/icons/spinner";
import { Button } from "@/components/ui/button";
import { Kbd } from "@/components/ui/kbd";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { toast } from "@/components/ui/use-toast";
import { useResolvedMarimoConfig } from "@/core/config/config";
import { addPackage, getPackageList } from "@/core/network/requests";
import { isWasm } from "@/core/wasm/utils";
import { ErrorBanner } from "@/plugins/impl/common/error-banner";
import { cn } from "@/utils/cn";
import { SettingSubtitle } from "./common";

interface Package {
  name: string;
  minVersion?: string;
}

interface OptionalFeature {
  id: string;
  /**
   * Required packages to install for the feature to work.
   */
  packagesRequired: Package[];
  /**
   * Additional packages to install if installed through this UI.
   */
  additionalPackageInstalls: Package[];
  /**
   * Description of the feature.
   */
  description: string;
}

// Define the optional dependencies and their features
const OPTIONAL_DEPENDENCIES: OptionalFeature[] = [
  {
    id: "sql",
    packagesRequired: [{ name: "duckdb" }, { name: "sqlglot" }],
    additionalPackageInstalls: [{ name: "polars[pyarrow]" }],
    description: "SQL cells",
  },
  {
    id: "charts",
    packagesRequired: [{ name: "altair" }],
    additionalPackageInstalls: [],
    description: "Charts in datasource viewer",
  },
  {
    id: "fast-charts",
    packagesRequired: [{ name: "vegafusion" }, { name: "vl-convert-python" }],
    additionalPackageInstalls: [],
    description: "Fast server-side charts",
  },
  {
    id: "formatting",
    packagesRequired: [isWasm() ? { name: "black" } : { name: "ruff" }],
    additionalPackageInstalls: [],
    description: "Formatting",
  },
  {
    id: "ai",
    packagesRequired: [{ name: "openai" }],
    additionalPackageInstalls: [],
    description: "AI features",
  },
  {
    id: "ipy-export",
    packagesRequired: [{ name: "nbformat" }],
    additionalPackageInstalls: [],
    description: "Export as IPYNB",
  },
  {
    id: "testing",
    packagesRequired: [{ name: "pytest" }],
    additionalPackageInstalls: [],
    description: "Autorun unit tests",
  },
];

// Only available outside wasm
if (!isWasm()) {
  OPTIONAL_DEPENDENCIES.push({
    id: "lsp",
    packagesRequired: [{ name: "python-lsp-server" }, { name: "websockets" }],
    additionalPackageInstalls: [{ name: "python-lsp-ruff" }],
    description: "Language Server Protocol*",
  });
}

export const OptionalFeatures: React.FC = () => {
  const [config] = useResolvedMarimoConfig();
  const packageManager = config.package_management.manager;
  const {
    data: installedPackageNames,
    error,
    refetch,
    isPending,
  } = useQuery({
    queryKey: ["getPackageList"],
    queryFn: getPackageList,
    select: ({ packages }) => new Set(packages.map((pkg) => pkg.name)),
  });

  if (isPending) {
    return <Spinner size="medium" centered={true} />;
  }

  if (error) {
    return <ErrorBanner error={error} />;
  }

  const installedPackages = data?.packages || [];
  const installedPackageNames = new Set(
    installedPackages.map((pkg) => pkg.name),
  );

  return (
    <div className="flex-1 flex flex-col overflow-hidden gap-2">
      <SettingSubtitle>Optional Features</SettingSubtitle>
      <p className="text-sm text-muted-foreground">
        marimo is lightweight, with few dependencies, to maximize compatibility
        with your own environments.
        <br />
        To unlock additional features in the marimo editor, you can install
        these optional dependencies:
      </p>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Dependency</TableHead>
            <TableHead>Feature</TableHead>
            <TableHead>Status</TableHead>
            <TableHead />
          </TableRow>
        </TableHeader>
        <TableBody>
          {OPTIONAL_DEPENDENCIES.map((dep) => {
            const isInstalled = dep.packagesRequired.every((pkg) =>
              installedPackageNames.has(pkg.name.split("[")[0]),
            );
            const packageSpec = dep.packagesRequired
              .map((pkg) => pkg.name)
              .join(", ");

            return (
              <TableRow key={dep.id} className="text-sm">
                <TableCell>{dep.description}</TableCell>
                <TableCell className="font-mono text-xs">
                  {packageSpec}
                </TableCell>
                <TableCell>
                  {isInstalled ? (
                    <div className="flex items-center">
                      <CheckCircleIcon className="h-4 w-4 text-[var(--grass-10)] mr-2" />
                      <span>Installed</span>
                    </div>
                  ) : (
                    <div className="flex items-center">
                      <XCircleIcon className="h-4 w-4 text-[var(--red-10)] mr-2" />
                      <InstallButton
                        packageSpecs={[
                          ...dep.packagesRequired,
                          ...dep.additionalPackageInstalls,
                        ]}
                        packageManager={packageManager}
                        onSuccess={refetch}
                      />
                    </div>
                  )}
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>

      <p className="text-muted-foreground mt-2">*Requires server restart</p>
    </div>
  );
};

const InstallButton: React.FC<{
  packageSpecs: Package[];
  packageManager: string;
  onSuccess: () => void;
}> = ({ packageSpecs, packageManager, onSuccess }) => {
  const [loading, setLoading] = React.useState(false);

  const handleInstall = async () => {
    try {
      setLoading(true);
      const packageSpec = packageSpecs
        .map((pkg) => {
          if (pkg.minVersion) {
            return `${pkg.name}>=${pkg.minVersion}`;
          }
          return pkg.name;
        })
        .join(" ");
      const response = await addPackage({ package: packageSpec });
      if (response.success) {
        onSuccess();
        toast({
          title: "Package installed",
          description: (
            <span>
              The packages{" "}
              <Kbd className="inline">
                {packageSpecs.map((pkg) => pkg.name).join(", ")}
              </Kbd>{" "}
              have been added to your environment.
            </span>
          ),
        });
      } else {
        toast({
          title: "Failed to install package",
          description: response.error,
          variant: "danger",
        });
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <Button
      size="xs"
      variant="outline"
      className={cn("text-xs", loading && "opacity-50 cursor-not-allowed")}
      onClick={handleInstall}
      disabled={loading}
    >
      {loading ? (
        <Spinner size="small" className="mr-2 h-3 w-3" />
      ) : (
        <BoxIcon className="mr-2 h-3 w-3" />
      )}
      Install with {packageManager}
    </Button>
  );
};
