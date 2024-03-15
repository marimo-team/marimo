/* Copyright 2024 Marimo. All rights reserved. */

import { RuntimeState } from "@/core/kernel/RuntimeState";
import { sendInstallMissingPackages } from "@/core/network/requests";
import {
  useAlerts,
  useAlertActions,
  isMissingPackageAlert,
  isInstallingPackageAlert,
} from "@/core/alerts/state";
import { logNever } from "@/utils/assertNever";
import { Banner } from "@/plugins/impl/common/error-banner";
import {
  PackageXIcon,
  BoxIcon,
  BoxesIcon,
  DownloadCloudIcon,
  PackageCheckIcon,
  XIcon,
} from "lucide-react";
import React from "react";
import { Button } from "../ui/button";
//import { useRestartKernel } from "./actions/useRestartKernel";

// TODO On install click, installation alert removed and instead we render installation progress ...
// - check mark if package installation succeeded
// - packageXIcon if failed
// - installation logs stay in terminal for now ... TODO to route to frontend
export const PackageAlert: React.FC = (props) => {
  const { packageAlert } = useAlerts();
  const { addPackageAlert, clearPackageAlert } = useAlertActions();

  if (packageAlert === null) {
    return null;
  }

  if (isMissingPackageAlert(packageAlert)) {
    return (
      <div className="flex flex-col gap-4 mb-5 fixed top-5 left-5 w-[400px] z-[200]">
        <Banner kind="danger" className="flex flex-col rounded py-3 px-5">
          <div className="flex justify-between">
            <span className="font-bold text-lg flex items-center mb-2">
              <PackageXIcon className="w-5 h-5 inline-block mr-2" />
              Missing packages
            </span>
            <Button
              variant="text"
              size="icon"
              onClick={() => clearPackageAlert()}
            >
              <XIcon className="w-5 h-5" />
            </Button>
          </div>
          <div className="flex flex-col gap-4 justify-between items-start text-muted-foreground">
            <div>
              <p>The following modules were not found:</p>
              <ul className="list-disc ml-4 mt-1">
                {packageAlert.packages.map((pkg) => (
                  <li className="flex items-center gap-1 font-mono">
                    <BoxIcon size="1rem" />
                    {pkg}
                  </li>
                ))}
              </ul>
            </div>
            <div className="ml-auto">
              <InstallPackagesButton
                packages={packageAlert.packages}
                addPackageAlert={addPackageAlert}
              />
            </div>
          </div>
        </Banner>
      </div>
    );
  } else if (isInstallingPackageAlert(packageAlert)) {
    console.log(packageAlert.packages);
    const title = "Installing packages";
    const titleIcon = (
      <DownloadCloudIcon className="w-5 h-5 inline-block mr-2" />
    );
    return (
      <div className="flex flex-col gap-4 mb-5 fixed top-5 left-5 w-[400px] z-[200]">
        <Banner kind="info" className="flex flex-col rounded pt-3 pb-4 px-5">
          <div className="flex justify-between">
            <span className="font-bold text-lg flex items-center mb-2">
              {titleIcon}
              {title}
            </span>
            <Button
              variant="text"
              size="icon"
              onClick={() => clearPackageAlert()}
            >
              <XIcon className="w-5 h-5" />
            </Button>
          </div>
          <div className="flex flex-col gap-4 justify-between items-start text-muted-foreground">
            <div>
              <ul className="list-disc ml-4 mt-1">
                {Object.entries(packageAlert.packages).map(
                  ([pkg, status], index) => (
                    <li
                      className="flex items-center gap-1 font-mono"
                      key={index}
                    >
                      <ProgressIcon status={status} />
                      {pkg}
                    </li>
                  )
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

const ProgressIcon = ({
  status,
}: {
  status: "queued" | "installing" | "installed" | "failed";
}) => {
  switch (status) {
    case "queued":
      return <BoxIcon size="1rem" />;
    case "installing":
      return <DownloadCloudIcon size="1rem" />;
    case "installed":
      return <PackageCheckIcon size="1rem" />;
    case "failed":
      return <PackageXIcon size="1rem" />;
    default:
      logNever(status);
      return null;
  }
};

async function installPackages(packages: string[], addPackageAlert: any) {
  const packageStatus = Object.fromEntries(
    packages.map((pkg) => [pkg, "queued"])
  );
  addPackageAlert({
    kind: "installing",
    packages: packageStatus,
  });
  RuntimeState.INSTANCE.registerRunStart();
  await sendInstallMissingPackages({});
}

const InstallPackagesButton = ({
  packages,
  addPackageAlert,
}: {
  packages: string[];
  addPackageAlert: any;
}) => {
  //const restartKernel = useRestartKernel();
  return (
    //<Button variant="outline" size="sm" onClick={restartKernel}>
    <Button
      variant="outline"
      size="sm"
      onClick={() => installPackages(packages, addPackageAlert)}
    >
      <DownloadCloudIcon className="w-4 h-4 mr-2" />
      <span className="font-semibold">Install with pip</span>
    </Button>
  );
};
