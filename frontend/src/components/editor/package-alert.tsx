/* Copyright 2024 Marimo. All rights reserved. */

import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormMessage,
} from "@/components/ui/form";
import { saveUserConfig } from "@/core/network/requests";
import {
  type UserConfig,
  UserConfigSchema,
} from "../../core/config/config-schema";
import { NativeSelect } from "../ui/native-select";
import { cn } from "@/utils/cn";
import { sendInstallMissingPackages } from "@/core/network/requests";
import {
  useAlerts,
  useAlertActions,
  isMissingPackageAlert,
  isInstallingPackageAlert,
} from "@/core/alerts/state";
import { Banner } from "@/plugins/impl/common/error-banner";
import {
  PackageXIcon,
  BoxIcon,
  CheckIcon,
  DownloadCloudIcon,
  PackageCheckIcon,
  XIcon,
  PlusIcon,
} from "lucide-react";
import type React from "react";
import { Button } from "../ui/button";
import type { PackageInstallationStatus } from "@/core/kernel/messages";
import { logNever } from "@/utils/assertNever";
import { useResolvedMarimoConfig } from "@/core/config/config";
import { isWasm } from "@/core/wasm/utils";
import {
  type PackageManagerName,
  PackageManagerNames,
} from "../../core/config/config-schema";
import { Logger } from "@/utils/Logger";
import { useAsyncData } from "@/hooks/useAsyncData";
import { Tooltip } from "../ui/tooltip";
import { useState } from "react";
import { cleanPythonModuleName, reverseSemverSort } from "@/utils/versions";
import { ExternalLink } from "../ui/links";
import * as z from "zod";
import { Popover, PopoverContent, PopoverTrigger } from "../ui/popover";

// Utility functions for parsing package specifiers
function parsePackageSpecifier(spec: string): {
  name: string;
  extras: string[];
} {
  const match = spec.match(/^([^[]+)(?:\[([^\]]+)])?$/);
  if (!match) {
    return { name: spec, extras: [] };
  }
  const [, name, extrasStr] = match;
  const extras = extrasStr ? extrasStr.split(",").map((e) => e.trim()) : [];
  return { name, extras };
}

function buildPackageSpecifier(name: string, extras: string[]): string {
  if (extras.length === 0) {
    return name;
  }
  return `${name}[${extras.join(",")}]`;
}

export const PackageAlert: React.FC = () => {
  const { packageAlert } = useAlerts();
  const { clearPackageAlert } = useAlertActions();
  const [userConfig] = useResolvedMarimoConfig();
  const [desiredPackageVersions, setDesiredPackageVersions] = useState<
    Record<string, string>
  >({});
  const [selectedExtras, setSelectedExtras] = useState<
    Record<string, string[]>
  >({});

  if (packageAlert === null) {
    return null;
  }

  const doesSupportVersioning =
    userConfig.package_management.manager !== "pixi";

  if (isMissingPackageAlert(packageAlert)) {
    return (
      <div className="flex flex-col gap-4 mb-5 fixed top-5 left-12 min-w-[400px] z-[200] opacity-95">
        <Banner
          kind="danger"
          className="flex flex-col rounded py-3 px-5 animate-in slide-in-from-left"
        >
          <div className="flex justify-between">
            <span className="font-bold text-lg flex items-center mb-2">
              <PackageXIcon className="w-5 h-5 inline-block mr-2" />
              Missing packages
            </span>
            <Button
              variant="text"
              data-testid="remove-banner-button"
              size="icon"
              onClick={() => clearPackageAlert(packageAlert.id)}
            >
              <XIcon className="w-5 h-5" />
            </Button>
          </div>
          <div className="flex flex-col gap-4 justify-between items-start text-muted-foreground text-base">
            <div>
              <p>The following packages were not found:</p>
              <ul className="list-disc ml-4 mt-1">
                {packageAlert.packages.map((pkg, index) => {
                  const parsed = parsePackageSpecifier(pkg);
                  const currentExtras = selectedExtras[pkg] || parsed.extras;

                  return (
                    <li
                      className="flex items-center gap-2 font-mono text-sm"
                      key={index}
                    >
                      <BoxIcon size="1rem" />

                      <ExtrasSelector
                        packageName={parsed.name}
                        selectedExtras={currentExtras}
                        onExtrasChange={(extras) =>
                          setSelectedExtras((prev) => ({
                            ...prev,
                            [pkg]: extras,
                          }))
                        }
                      />

                      {doesSupportVersioning && (
                        <PackageVersionSelect
                          value={desiredPackageVersions[pkg] ?? "latest"}
                          onChange={(value) =>
                            setDesiredPackageVersions((prev) => ({
                              ...prev,
                              [pkg]: value,
                            }))
                          }
                          packageName={parsed.name}
                        />
                      )}
                    </li>
                  );
                })}
              </ul>
            </div>
            <div className="ml-auto flex flex-row items-baseline">
              {packageAlert.isolated ? (
                <>
                  <InstallPackagesButton
                    manager={userConfig.package_management.manager}
                    packages={packageAlert.packages.map((pkg) => {
                      const parsed = parsePackageSpecifier(pkg);
                      const currentExtras =
                        selectedExtras[pkg] || parsed.extras;
                      return buildPackageSpecifier(parsed.name, currentExtras);
                    })}
                    versions={desiredPackageVersions}
                    clearPackageAlert={() => clearPackageAlert(packageAlert.id)}
                  />

                  {!isWasm() && (
                    <>
                      <span className="px-2 text-sm">with</span>{" "}
                      <PackageManagerForm />
                    </>
                  )}
                </>
              ) : (
                <p>
                  If you set up a{" "}
                  <ExternalLink href="https://docs.python.org/3/tutorial/venv.html#creating-virtual-environments">
                    virtual environment
                  </ExternalLink>
                  , marimo can install these packages for you.
                </p>
              )}
            </div>
          </div>
        </Banner>
      </div>
    );
  }

  if (isInstallingPackageAlert(packageAlert)) {
    const { status, title, titleIcon, description } =
      getInstallationStatusElements(packageAlert.packages);
    if (status === "installed") {
      setTimeout(() => clearPackageAlert(packageAlert.id), 10_000);
    }

    return (
      <div className="flex flex-col gap-4 mb-5 fixed top-5 left-12 min-w-[400px] z-[200] opacity-95">
        <Banner
          kind={status === "failed" ? "danger" : "info"}
          className="flex flex-col rounded pt-3 pb-4 px-5"
        >
          <div className="flex justify-between">
            <span className="font-bold text-lg flex items-center mb-2">
              {titleIcon}
              {title}
            </span>
            <Button
              variant="text"
              data-testid="remove-banner-button"
              size="icon"
              onClick={() => clearPackageAlert(packageAlert.id)}
            >
              <XIcon className="w-5 h-5" />
            </Button>
          </div>
          <div
            className={cn(
              "flex flex-col gap-4 justify-between items-start text-muted-foreground text-base",
              status === "installed" && "text-accent-foreground",
            )}
          >
            <div>
              <p>{description}</p>
              <ul className="list-disc ml-4 mt-1">
                {Object.entries(packageAlert.packages).map(
                  ([pkg, st], index) => (
                    <li
                      className={cn(
                        "flex items-center gap-1 font-mono text-sm",
                        st === "installing" && "font-semibold",
                        st === "failed" && "text-destructive",
                        st === "installed" && "text-accent-foreground",
                        st === "installed" &&
                          status === "failed" &&
                          "text-muted-foreground",
                      )}
                      key={index}
                    >
                      <ProgressIcon status={st} />
                      {pkg}
                    </li>
                  ),
                )}
              </ul>
            </div>
          </div>
        </Banner>
      </div>
    );
  }

  logNever(packageAlert);
  return null;
};

function getInstallationStatusElements(packages: PackageInstallationStatus) {
  const statuses = new Set(Object.values(packages));
  const status =
    statuses.has("queued") || statuses.has("installing")
      ? "installing"
      : statuses.has("failed")
        ? "failed"
        : "installed";

  if (status === "installing") {
    return {
      status: "installing",
      title: "Installing packages",
      titleIcon: <DownloadCloudIcon className="w-5 h-5 inline-block mr-2" />,
      description: "Installing packages:",
    };
  }
  if (status === "installed") {
    return {
      status: "installed",
      title: "All packages installed!",
      titleIcon: <PackageCheckIcon className="w-5 h-5 inline-block mr-2" />,
      description: "Installed packages:",
    };
  }
  return {
    status: "failed",
    title: "Some packages failed to install",
    titleIcon: <PackageXIcon className="w-5 h-5 inline-block mr-2" />,
    description: "See terminal for error logs.",
  };
}

const ProgressIcon = ({
  status,
}: {
  status: PackageInstallationStatus[string];
}) => {
  switch (status) {
    case "queued":
      return <BoxIcon size="1rem" />;
    case "installing":
      return <DownloadCloudIcon size="1rem" />;
    case "installed":
      return <CheckIcon size="1rem" />;
    case "failed":
      return <XIcon size="1rem" />;
    default:
      logNever(status);
      return null;
  }
};

const InstallPackagesButton = ({
  manager,
  packages,
  versions,
  clearPackageAlert,
}: {
  manager: PackageManagerName;
  packages: string[];
  versions: Record<string, string>;
  clearPackageAlert: () => void;
}) => {
  return (
    <Button
      variant="outline"
      data-testid="install-packages-button"
      size="sm"
      onClick={async () => {
        clearPackageAlert();

        // Empty version implies latest
        const completePackages = { ...versions };
        for (const pkg of packages) {
          completePackages[pkg] = completePackages[pkg] ?? "";
        }

        await sendInstallMissingPackages({
          manager,
          versions: completePackages,
        }).catch((error) => {
          Logger.error(error);
        });
      }}
    >
      <DownloadCloudIcon className="w-4 h-4 mr-2" />
      <span className="font-semibold">Install</span>
    </Button>
  );
};

const PackageManagerForm: React.FC = () => {
  const [config, setConfig] = useResolvedMarimoConfig();

  // Create form
  const form = useForm<UserConfig>({
    resolver: zodResolver(UserConfigSchema),
    defaultValues: config,
  });

  const onSubmit = async (values: UserConfig) => {
    await saveUserConfig({ config: values }).then(() => {
      setConfig(values);
    });
  };

  return (
    <Form {...form}>
      <form
        onChange={form.handleSubmit(onSubmit)}
        className="flex flex-col gap-5"
      >
        <div className="flex flex-col gap-3">
          <FormField
            control={form.control}
            name="package_management.manager"
            render={({ field }) => (
              <FormItem>
                <FormControl>
                  <NativeSelect
                    data-testid="install-package-manager-select"
                    onChange={(e) => field.onChange(e.target.value)}
                    value={field.value}
                    disabled={field.disabled}
                    className="inline-flex mr-2"
                  >
                    {PackageManagerNames.map((option) => (
                      <option value={option} key={option}>
                        {option}
                      </option>
                    ))}
                  </NativeSelect>
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
        </div>
      </form>
    </Form>
  );
};

interface PackageVersionSelectProps {
  value: string;
  onChange: (value: string) => void;
  packageName: string;
}

const PyPiPackageResponse = z.object({
  info: z.object({
    provides_extra: z.string().array().nullable(),
  }),
  releases: z.record(z.string(), z.unknown()),
});

interface ExtrasSelectorProps {
  packageName: string;
  selectedExtras: string[];
  onExtrasChange: (extras: string[]) => void;
}

const ExtrasSelector: React.FC<ExtrasSelectorProps> = ({
  packageName,
  selectedExtras,
  onExtrasChange,
}) => {
  const [isOpen, setIsOpen] = useState(false);

  const {
    data: availableExtras = [],
    loading,
    error,
  } = useAsyncData(async () => {
    const response = await fetch(
      `https://pypi.org/pypi/${cleanPythonModuleName(packageName)}/json`,
      {
        method: "GET",
        signal: AbortSignal.timeout(5000), // 5s timeout
      },
    );
    const pkgInfo = PyPiPackageResponse.parse(await response.json());
    return pkgInfo.info.provides_extra || [];
  }, [packageName]);

  const handleExtraToggle = (extra: string, checked: boolean) => {
    if (checked) {
      onExtrasChange([...selectedExtras, extra]);
    } else {
      onExtrasChange(selectedExtras.filter((e) => e !== extra));
    }
  };

  return (
    <div className="flex items-center max-w-72">
      <span className="shrink-0">{packageName}</span>

      {selectedExtras.length > 0 ? (
        <span className="flex items-center min-w-0 flex-1">
          <span className="shrink-0">[</span>
          <Popover open={isOpen} onOpenChange={setIsOpen}>
            <PopoverTrigger asChild={true}>
              <button
                className="hover:bg-muted/50 rounded text-sm px-1 transition-colors border border-muted-foreground/30 hover:border-muted-foreground/60 min-w-0 flex-1 truncate text-left"
                title={`Selected extras: ${selectedExtras.join(", ")}`}
              >
                {selectedExtras.join(",")}
              </button>
            </PopoverTrigger>
            <PopoverContent className="w-64 p-0" align="start">
              <div className="p-2">
                <div className="flex flex-wrap gap-1 p-1 min-h-[24px]">
                  {selectedExtras.length > 0 ? (
                    selectedExtras.map((extra) => (
                      <span
                        key={extra}
                        className="inline-flex items-center gap-1 px-1 py-0.5 text-sm font-mono border border-muted-foreground/30 hover:border-muted-foreground/60 rounded-sm cursor-pointer group transition-colors"
                        onClick={() => handleExtraToggle(extra, false)}
                      >
                        {extra}
                        <XIcon className="w-3 h-3 opacity-60 group-hover:opacity-100" />
                      </span>
                    ))
                  ) : (
                    <span className="text-muted-foreground italic text-sm">
                      Package extras
                    </span>
                  )}
                </div>
              </div>

              {availableExtras.length > 0 && (
                <div className="border-t border-border" />
              )}

              <div className="space-y-1 max-h-48 overflow-auto px-2">
                {availableExtras.map((extra) => (
                  <div
                    key={extra}
                    className="flex items-center space-x-2 px-2 py-1.5 hover:bg-accent hover:text-accent-foreground rounded-sm relative pl-8 cursor-pointer aria-selected:bg-accent aria-selected:text-accent-foreground"
                    aria-selected={selectedExtras.includes(extra)}
                    onClick={() =>
                      handleExtraToggle(extra, !selectedExtras.includes(extra))
                    }
                  >
                    {selectedExtras.includes(extra) && (
                      <CheckIcon className="absolute left-2 h-4 w-4" />
                    )}
                    <span className="text-sm font-mono flex-1">{extra}</span>
                  </div>
                ))}
              </div>
            </PopoverContent>
          </Popover>
          <span className="shrink-0">]</span>
        </span>
      ) : loading || error || availableExtras.length === 0 ? null : (
        <Popover open={isOpen} onOpenChange={setIsOpen}>
          <PopoverTrigger asChild={true}>
            <button
              className="hover:bg-muted/50 rounded text-sm ml-2 transition-colors border border-muted-foreground/30 hover:border-muted-foreground/60 h-5 w-5 flex items-center justify-center p-0"
              title="Add extras"
            >
              <PlusIcon className="w-3 h-3 flex-shrink-0" />
            </button>
          </PopoverTrigger>
          <PopoverContent className="w-64 p-0" align="start">
            <div className="p-2">
              <div className="flex flex-wrap gap-1 p-1 min-h-[24px]">
                <span className="text-muted-foreground italic text-sm">
                  Package extras
                </span>
              </div>
            </div>

            <div className="border-t border-border" />

            <div className="space-y-1 max-h-48 overflow-auto px-2">
              {availableExtras.map((extra) => (
                <div
                  key={extra}
                  className="flex items-center space-x-2 px-2 py-1.5 hover:bg-accent hover:text-accent-foreground rounded-sm relative pl-8 cursor-pointer aria-selected:bg-accent aria-selected:text-accent-foreground"
                  aria-selected={selectedExtras.includes(extra)}
                  onClick={() =>
                    handleExtraToggle(extra, !selectedExtras.includes(extra))
                  }
                >
                  {selectedExtras.includes(extra) && (
                    <CheckIcon className="absolute left-2 h-4 w-4" />
                  )}
                  <span className="text-sm font-mono flex-1">{extra}</span>
                </div>
              ))}
            </div>
          </PopoverContent>
        </Popover>
      )}
    </div>
  );
};

const PackageVersionSelect: React.FC<PackageVersionSelectProps> = ({
  value,
  onChange,
  packageName,
}) => {
  const {
    data = [],
    loading,
    error,
  } = useAsyncData(async () => {
    const response = await fetch(
      `https://pypi.org/pypi/${cleanPythonModuleName(packageName)}/json`,
      {
        method: "GET",
        signal: AbortSignal.timeout(5000), // 5s timeout
      },
    );
    const pkgInfo = PyPiPackageResponse.parse(await response.json());
    const versions = Object.keys(pkgInfo.releases).toSorted(reverseSemverSort);
    // Add latest, limit to 100 versions
    return ["latest", ...versions.slice(0, 100)];
  }, [packageName]);

  if (error) {
    return (
      <Tooltip content="Failed to fetch package versions">
        <NativeSelect
          value={value}
          onChange={(e) => onChange(e.target.value)}
          disabled={true}
          className="inline-flex ml-2 w-24 text-ellipsis"
        >
          <option value="latest">latest</option>
        </NativeSelect>
      </Tooltip>
    );
  }

  return (
    <NativeSelect
      value={value}
      onChange={(e) => onChange(e.target.value)}
      disabled={loading}
      className="inline-flex ml-2 w-24 text-ellipsis"
    >
      {loading ? (
        <option value="latest">latest</option>
      ) : (
        data.map((version) => (
          <option value={version} key={version}>
            {version}
          </option>
        ))
      )}
    </NativeSelect>
  );
};
