/* Copyright 2024 Marimo. All rights reserved. */
import { useAtomValue, useSetAtom } from "jotai";
import {
  BoxIcon,
  ChevronDownIcon,
  ChevronRightIcon,
  HelpCircleIcon,
} from "lucide-react";
import React from "react";
import { useOpenSettingsToTab } from "@/components/app-config/state";
import { Spinner } from "@/components/icons/spinner";
import { SearchInput } from "@/components/ui/input";
import { Kbd } from "@/components/ui/kbd";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Tooltip } from "@/components/ui/tooltip";
import { toast } from "@/components/ui/use-toast";
import { useResolvedMarimoConfig } from "@/core/config/config";
import {
  addPackage,
  getDependencyTree,
  getPackageList,
  removePackage,
} from "@/core/network/requests";
import type { DependencyTreeNode } from "@/core/network/types";
import { isWasm } from "@/core/wasm/utils";
import { useAsyncData } from "@/hooks/useAsyncData";
import { ErrorBanner } from "@/plugins/impl/common/error-banner";
import { cn } from "@/utils/cn";
import { copyToClipboard } from "@/utils/copy";
import { Events } from "@/utils/events";
import { PACKAGES_INPUT_ID } from "./constants";
import { PanelEmptyState } from "./empty-state";
import { packagesToInstallAtom } from "./packages-state";

const showAddPackageToast = (packageName: string, error?: string | null) => {
  if (error) {
    toast({
      title: "Failed to add package",
      description: error,
      variant: "danger",
    });
  } else {
    toast({
      title: "Package added",
      description: (
        <div>
          <div>
            The package <Kbd className="inline">{packageName}</Kbd> and its
            dependencies has been added to your environment.
          </div>
          <div className="text-xs text-muted-foreground mt-1">
            Some Python packages may require a kernel restart to see changes.
          </div>
        </div>
      ),
    });
  }
};

const showUpgradePackageToast = (
  packageName: string,
  error?: string | null,
) => {
  if (error) {
    toast({
      title: "Failed to upgrade package",
      description: error,
      variant: "danger",
    });
  } else {
    toast({
      title: "Package upgraded",
      description: (
        <div>
          <div>
            The package <Kbd className="inline">{packageName}</Kbd> has been
            upgraded.
          </div>
          <div className="text-xs text-muted-foreground mt-1">
            Some Python packages may require a kernel restart to see changes.
          </div>
        </div>
      ),
    });
  }
};

const showRemovePackageToast = (packageName: string, error?: string | null) => {
  if (error) {
    toast({
      title: "Failed to remove package",
      description: error,
      variant: "danger",
    });
  } else {
    toast({
      title: "Package removed",
      description: (
        <div>
          <div>
            The package <Kbd className="inline">{packageName}</Kbd> has been
            removed from your environment.
          </div>
          <div className="text-xs text-muted-foreground mt-1">
            Some Python packages may require a kernel restart to see changes.
          </div>
        </div>
      ),
    });
  }
};

const PackageActionButton: React.FC<{
  onClick: () => void;
  loading: boolean;
  children: React.ReactNode;
  className?: string;
}> = ({ onClick, loading, children, className }) => {
  if (loading) {
    return <Spinner size="small" className="h-4 w-4 shrink-0 opacity-50" />;
  }

  return (
    <button
      type="button"
      className={cn(
        "px-2 h-full text-xs text-muted-foreground hover:text-foreground",
        "invisible group-hover:visible",
        className,
      )}
      onClick={Events.stopPropagation(onClick)}
    >
      {children}
    </button>
  );
};

export const PackagesPanel: React.FC = () => {
  const [config] = useResolvedMarimoConfig();
  const packageManager = config.package_management.manager;
  const { data, error, refetch, isPending } = useAsyncData(
    () => getPackageList(),
    [packageManager],
  );

  const {
    data: treeData,
    error: treeError,
    refetch: refetchTree,
  } = useAsyncData(() => getDependencyTree(), [packageManager]);

  const [viewMode, setViewMode] = React.useState<"list" | "tree">("tree");

  const isTreeSupported = treeData?.tree != null;

  // Set default view mode and handle unsupported cases
  const [hasInitialized, setHasInitialized] = React.useState(false);

  React.useEffect(() => {
    if (!hasInitialized && treeData !== undefined) {
      // On initial load, prefer tree view if supported
      if (isTreeSupported) {
        setViewMode("tree");
      } else {
        setViewMode("list");
      }
      setHasInitialized(true);
    } else if (hasInitialized && !isTreeSupported && viewMode === "tree") {
      // If user is on tree view but it becomes unsupported, switch to list
      setViewMode("list");
    }
  }, [isTreeSupported, viewMode, treeData, hasInitialized]);

  const handleRefetch = () => {
    refetch();
    refetchTree();
  };

  // Only show on the first load
  if (isPending) {
    return <Spinner size="medium" centered={true} />;
  }

  if (error) {
    return <ErrorBanner error={error} />;
  }

  const packages = data?.packages || [];

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      <InstallPackageForm
        packageManager={packageManager}
        onSuccess={handleRefetch}
      />
      {isTreeSupported && (
        <div className="flex items-center justify-between px-2 py-1 border-b">
          <div className="flex gap-1">
            <button
              type="button"
              className={cn(
                "px-2 py-1 text-xs rounded",
                viewMode === "list"
                  ? "bg-accent text-accent-foreground"
                  : "text-muted-foreground hover:text-foreground",
              )}
              onClick={() => setViewMode("list")}
            >
              List
            </button>
            <button
              type="button"
              className={cn(
                "px-2 py-1 text-xs rounded",
                viewMode === "tree"
                  ? "bg-accent text-accent-foreground"
                  : "text-muted-foreground hover:text-foreground",
              )}
              onClick={() => setViewMode("tree")}
            >
              Tree
            </button>
          </div>
          <div className="flex items-center gap-2">
            <div
              className="items-center border px-2 py-0.5 text-xs transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 text-foreground rounded-sm text-ellipsis block overflow-hidden max-w-fit font-medium"
              title={treeData?.tree?.name === "<root>" ? "sandbox" : "project"}
            >
              {treeData?.tree?.name === "<root>" ? "sandbox" : "project"}
            </div>
            {treeData?.tree?.name !== "<root>" && treeData?.tree?.name && (
              <span className="text-xs text-muted-foreground">
                {treeData.tree.name}
                {treeData?.tree?.version && ` v${treeData.tree.version}`}
              </span>
            )}
          </div>
        </div>
      )}
      {viewMode === "list" || !isTreeSupported ? (
        <PackagesList packages={packages} onSuccess={handleRefetch} />
      ) : (
        <DependencyTree
          tree={treeData?.tree ?? undefined}
          error={treeError}
          onSuccess={handleRefetch}
        />
      )}
    </div>
  );
};

const InstallPackageForm: React.FC<{
  packageManager: string;
  onSuccess: () => void;
}> = ({ onSuccess, packageManager }) => {
  const [input, setInput] = React.useState("");
  const [loading, setLoading] = React.useState(false);
  const { handleClick: openSettings } = useOpenSettingsToTab();

  // Get the packages to install from the atom
  const packagesToInstall = useAtomValue(packagesToInstallAtom);
  const setPackagesToInstall = useSetAtom(packagesToInstallAtom);

  // Set the input value when packagesToInstall changes
  React.useEffect(() => {
    if (packagesToInstall) {
      setInput(packagesToInstall);
      // Clear the atom after setting the input
      setPackagesToInstall(null);
    }
  }, [packagesToInstall, setPackagesToInstall]);

  const handleAddPackage = async () => {
    try {
      setLoading(true);
      const packages = input.split(",").map((p) => p.trim());
      for (const [idx, packageName] of packages.entries()) {
        const response = await addPackage({ package: packageName });
        if (response.success) {
          showAddPackageToast(packageName);
        } else {
          showAddPackageToast(packageName, response.error);
        }
        // Wait 1s if there are more packages to install
        if (idx < packages.length - 1) {
          await new Promise((resolve) => setTimeout(resolve, 1000));
        }
      }
      onSuccess();
    } finally {
      setInput("");
      setLoading(false);
    }
  };

  return (
    <div className="flex items-center w-full border-b">
      <SearchInput
        placeholder={`Install packages with ${packageManager}...`}
        id={PACKAGES_INPUT_ID}
        icon={
          loading ? (
            <Spinner
              size="small"
              className="mr-2 h-4 w-4 shrink-0 opacity-50"
            />
          ) : (
            <Tooltip content="Change package manager">
              <BoxIcon
                onClick={() => openSettings("packageManagement")}
                className="mr-2 h-4 w-4 shrink-0 opacity-50 hover:opacity-80 cursor-pointer"
              />
            </Tooltip>
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
            <TableCell className="flex justify-end">
              <UpgradeButton packageName={item.name} onSuccess={onSuccess} />
              <RemoveButton packageName={item.name} onSuccess={onSuccess} />
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
};

const UpgradeButton: React.FC<{
  packageName: string;
  onSuccess: () => void;
}> = ({ packageName, onSuccess }) => {
  const [loading, setLoading] = React.useState(false);

  // Hide upgrade button in WASM
  if (isWasm()) {
    return null;
  }

  const handleUpgradePackage = async () => {
    try {
      setLoading(true);
      const response = await addPackage({
        package: packageName,
        upgrade: true,
      });
      if (response.success) {
        onSuccess();
        showUpgradePackageToast(packageName);
      } else {
        showUpgradePackageToast(packageName, response.error);
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <PackageActionButton onClick={handleUpgradePackage} loading={loading}>
      Upgrade
    </PackageActionButton>
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
        showRemovePackageToast(packageName);
      } else {
        showRemovePackageToast(packageName, response.error);
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <PackageActionButton onClick={handleRemovePackage} loading={loading}>
      Remove
    </PackageActionButton>
  );
};

const DependencyTree: React.FC<{
  tree?: DependencyTreeNode;
  error?: Error | null;
  onSuccess: () => void;
}> = ({ tree, error, onSuccess }) => {
  const [expandedNodes, setExpandedNodes] = React.useState<Set<string>>(
    new Set(),
  );

  // Reset tree to collapsed state when tree data changes (including refetches)
  React.useEffect(() => {
    setExpandedNodes(new Set());
  }, [tree]);

  if (error) {
    return <ErrorBanner error={error} />;
  }

  if (!tree) {
    return <Spinner size="medium" centered={true} />;
  }

  if (tree.dependencies.length === 0) {
    return (
      <PanelEmptyState
        title="No dependencies"
        description="No package dependencies found in this environment."
        icon={<BoxIcon />}
      />
    );
  }

  const toggleNode = (nodeId: string) => {
    setExpandedNodes((prev) => {
      const newSet = new Set(prev);
      if (newSet.has(nodeId)) {
        newSet.delete(nodeId);
      } else {
        newSet.add(nodeId);
      }
      return newSet;
    });
  };

  return (
    <div className="flex-1 overflow-auto">
      <div>
        {tree.dependencies.map((dep, index) => (
          <div key={`${dep.name}-${index}`} className="border-b">
            <DependencyTreeNode
              nodeId={`root-${index}`}
              node={dep}
              level={0}
              isTopLevel={true}
              expandedNodes={expandedNodes}
              onToggle={toggleNode}
              onSuccess={onSuccess}
            />
          </div>
        ))}
      </div>
    </div>
  );
};

const DependencyTreeNode: React.FC<{
  nodeId: string;
  node: DependencyTreeNode;
  level: number;
  isTopLevel?: boolean;
  expandedNodes: Set<string>;
  onToggle: (nodeId: string) => void;
  onSuccess: () => void;
}> = ({
  nodeId,
  node,
  level,
  isTopLevel = false,
  expandedNodes,
  onToggle,
  onSuccess,
}) => {
  const hasChildren = node.dependencies.length > 0;
  const isExpanded = expandedNodes.has(nodeId);
  const indent = isTopLevel ? 0 : 16 + level * 16; // Top-level uses CSS padding, children use calculated indent

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      if (hasChildren) {
        onToggle(nodeId);
      }
    }
    // Allow arrow keys to bubble up for tree navigation
  };

  const handleClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (hasChildren) {
      onToggle(nodeId);
    }
  };

  return (
    <div>
      <div
        className={cn(
          "flex items-center group cursor-pointer text-sm whitespace-nowrap",
          "hover:bg-[var(--slate-2)] focus:bg-[var(--slate-2)] focus:outline-none",
          hasChildren && "select-none",
          isTopLevel ? "px-2 py-1" : "",
        )}
        style={isTopLevel ? {} : { paddingLeft: `${indent}px` }}
        onClick={handleClick}
        onKeyDown={handleKeyDown}
        tabIndex={0}
        role="treeitem"
        aria-expanded={hasChildren ? isExpanded : undefined}
      >
        {/* Expand/collapse arrow */}
        {hasChildren ? (
          isExpanded ? (
            <ChevronDownIcon className="w-4 h-4 mr-2 flex-shrink-0" />
          ) : (
            <ChevronRightIcon className="w-4 h-4 mr-2 flex-shrink-0" />
          )
        ) : (
          <div className="w-4 mr-2 flex-shrink-0" />
        )}

        {/* Package info */}
        <div className="flex items-center gap-2 flex-1 min-w-0 py-1.5">
          <span className="font-medium truncate">{node.name}</span>
          {node.version && (
            <span className="text-muted-foreground text-xs">
              v{node.version}
            </span>
          )}
        </div>

        {/* Tags */}
        <div className="flex items-center gap-1 ml-2">
          {node.tags.map((tag, index) => {
            if (tag.kind === "cycle") {
              return (
                <div
                  key={index}
                  className="items-center border px-2 py-0.5 text-xs transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 text-foreground rounded-sm text-ellipsis block overflow-hidden max-w-fit font-medium border-orange-300 dark:border-orange-700 text-orange-700 dark:text-orange-300"
                  title="cycle"
                >
                  cycle
                </div>
              );
            }
            if (tag.kind === "extra") {
              return (
                <div
                  key={index}
                  className="items-center border px-2 py-0.5 text-xs transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 text-foreground rounded-sm text-ellipsis block overflow-hidden max-w-fit font-medium border-blue-300 dark:border-blue-700 text-blue-700 dark:text-blue-300"
                  title={tag.value}
                >
                  {tag.value}
                </div>
              );
            }
            if (tag.kind === "group") {
              return (
                <div
                  key={index}
                  className="items-center border px-2 py-0.5 text-xs transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 text-foreground rounded-sm text-ellipsis block overflow-hidden max-w-fit font-medium border-green-300 dark:border-green-700 text-green-700 dark:text-green-300"
                  title={tag.value}
                >
                  {tag.value}
                </div>
              );
            }
            return null;
          })}
        </div>

        {/* Actions for top-level packages */}
        {isTopLevel && (
          <div className="flex gap-1 invisible group-hover:visible mr-2">
            <UpgradeButton packageName={node.name} onSuccess={onSuccess} />
            <RemoveButton packageName={node.name} onSuccess={onSuccess} />
          </div>
        )}
      </div>

      {/* Children */}
      {hasChildren && isExpanded && (
        <div role="group">
          {node.dependencies.map((child, index) => (
            <DependencyTreeNode
              key={`${child.name}-${index}`}
              nodeId={`${nodeId}-${index}`}
              node={child}
              level={level + 1}
              isTopLevel={false}
              expandedNodes={expandedNodes}
              onToggle={onToggle}
              onSuccess={onSuccess}
            />
          ))}
        </div>
      )}
    </div>
  );
};
