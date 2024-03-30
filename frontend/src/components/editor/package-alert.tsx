/* Copyright 2024 Marimo. All rights reserved. */

import { zodResolver } from "@hookform/resolvers/zod";
import { DefaultValues, useForm } from "react-hook-form";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormMessage,
} from "@/components/ui/form";
import { saveUserConfig } from "@/core/network/requests";
import { UserConfig, UserConfigSchema } from "../../core/config/config-schema";
import { NativeSelect } from "../ui/native-select";
import { cn } from "@/utils/cn";
import { RuntimeState } from "@/core/kernel/RuntimeState";
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
} from "lucide-react";
import React from "react";
import { Button } from "../ui/button";
import { PackageInstallationStatus } from "@/core/kernel/messages";
import { logNever } from "@/utils/assertNever";
import { useUserConfig } from "@/core/config/config";
import { isPyodide } from "@/core/pyodide/utils";
import {
  PackageManagerName,
  PackageManagerNames,
} from "../../core/config/config-schema";

export const PackageAlert: React.FC = (props) => {
  const { packageAlert } = useAlerts();
  const { clearPackageAlert } = useAlertActions();
  const [userConfig] = useUserConfig();

  if (packageAlert === null) {
    return null;
  }

  if (isMissingPackageAlert(packageAlert)) {
    return (
      <div className="flex flex-col gap-4 mb-5 fixed top-5 left-5 w-[400px] z-[200] opacity-95">
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
                {packageAlert.packages.map((pkg, index) => (
                  <li
                    className="flex items-center gap-1 font-mono text-sm"
                    key={index}
                  >
                    <BoxIcon size="1rem" />
                    {pkg}
                  </li>
                ))}
              </ul>
            </div>
            <div className="ml-auto flex flex-row items-baseline">
              {packageAlert.isolated ? (
                <>
                  <InstallPackagesButton
                    manager={userConfig.package_management.manager}
                    clearPackageAlert={() => clearPackageAlert(packageAlert.id)}
                  />

                  {isPyodide() ? null : (
                    <>
                      <span className="px-2 text-sm">with</span>{" "}
                      <PackageManagerForm />
                    </>
                  )}
                </>
              ) : (
                <p>
                  If you set up a{" "}
                  <a
                    href="https://docs.python.org/3/tutorial/venv.html#creating-virtual-environments"
                    className="text-accent-foreground hover:underline"
                    target="_blank"
                    rel="noreferrer"
                  >
                    virtual environment
                  </a>
                  , marimo can install these packages for you.
                </p>
              )}
            </div>
          </div>
        </Banner>
      </div>
    );
  } else if (isInstallingPackageAlert(packageAlert)) {
    const { status, title, titleIcon, description } =
      getInstallationStatusElements(packageAlert.packages);
    if (status === "installed") {
      setTimeout(() => clearPackageAlert(packageAlert.id), 10_000);
    }

    return (
      <div className="flex flex-col gap-4 mb-5 fixed top-5 left-5 w-[400px] z-[200] opacity-95">
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
  } else {
    logNever(packageAlert);
    return null;
  }
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
  } else if (status === "installed") {
    return {
      status: "installed",
      title: "All packages installed!",
      titleIcon: <PackageCheckIcon className="w-5 h-5 inline-block mr-2" />,
      description: "Installed packages:",
    };
  } else {
    return {
      status: "failed",
      title: "Some packages failed to install",
      titleIcon: <PackageXIcon className="w-5 h-5 inline-block mr-2" />,
      description: "See terminal for error logs.",
    };
  }
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

async function installPackages(
  manager: PackageManagerName,
  clearPackageAlert: () => void,
) {
  clearPackageAlert();
  RuntimeState.INSTANCE.registerRunStart();
  await sendInstallMissingPackages({ manager: manager });
}

const InstallPackagesButton = ({
  manager,
  clearPackageAlert,
}: {
  manager: PackageManagerName;
  clearPackageAlert: () => void;
}) => {
  return (
    <Button
      variant="outline"
      data-testid="install-packages-button"
      size="sm"
      onClick={() => installPackages(manager, clearPackageAlert)}
    >
      <DownloadCloudIcon className="w-4 h-4 mr-2" />
      <span className="font-semibold">Install</span>
    </Button>
  );
};

export const PackageManagerForm: React.FC = () => {
  const [config, setConfig] = useUserConfig();

  // Create form
  const form = useForm<UserConfig>({
    resolver: zodResolver(UserConfigSchema),
    defaultValues: config as DefaultValues<UserConfig>,
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
