/* Copyright 2026 Marimo. All rights reserved. */
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
import { useRequestClient } from "@/core/network/requests";
import type {
  DependencyTreeNode,
  DependencyTreeResponse,
} from "@/core/network/types";
import { stripPackageManagerPrefix } from "@/core/packages/package-input-utils";
import {
  showRemovePackageToast,
  showUpgradePackageToast,
} from "@/core/packages/toast-components";
import { useInstallPackages } from "@/core/packages/useInstallPackage";
import { isWasm } from "@/core/wasm/utils";
import { useAsyncData } from "@/hooks/useAsyncData";
import { ErrorBanner } from "@/plugins/impl/common/error-banner";
import { cn } from "@/utils/cn";
import { copyToClipboard } from "@/utils/copy";
import { Events } from "@/utils/events";
import { PanelEmptyState } from "./empty-state";
import { PACKAGES_INPUT_ID, packagesToInstallAtom } from "./packages-utils";

type ViewMode = "tree" | "list";
type PackageInstallationContext = DependencyTreeResponse["context"];

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

const PackagesPanel: React.FC = () => {
  const [config] = useResolvedMarimoConfig();
  const packageManager = config.package_management.manager;
  const { getDependencyTree, getPackageList } = useRequestClient();

  const [userViewMode, setUserViewMode] = React.useState<ViewMode | null>(null);
  const {
    data: dependencies,
    error,
    refetch,
    isPending,
  } = useAsyncData(async () => {
    // A sandbox's list and tree both inspect the same environment. Wait for
    // the context before issuing the list request so sandboxes do that work
    // only once; non-sandbox managers still need both views.
    const dependencyTreeResponse = await getDependencyTree();
    if (dependencyTreeResponse.context.kind === "sandbox") {
      return {
        list: [],
        context: dependencyTreeResponse.context,
        tree: dependencyTreeResponse.tree,
      };
    }

    const listPackagesResponse = await getPackageList();
    return {
      list: listPackagesResponse.packages,
      context: dependencyTreeResponse.context,
      tree: dependencyTreeResponse.tree,
    };
  }, [packageManager]);

  // Only show on the first load
  if (isPending) {
    return <Spinner size="medium" centered={true} />;
  }

  if (error) {
    return <ErrorBanner error={error} />;
  }

  const isTreeSupported = dependencies.tree != null;
  const name = dependencies.tree?.name;
  const version = dependencies?.tree?.version;
  const sandboxBackend =
    dependencies.context.kind === "sandbox"
      ? dependencies.context.backend
      : null;
  const isSandbox = sandboxBackend !== null;
  const viewMode = isSandbox
    ? "tree"
    : resolveViewMode(userViewMode, isTreeSupported);
  const scopeLabel = sandboxBackend
    ? `${sandboxBackend} sandbox`
    : name && name !== "<root>"
      ? "project"
      : "environment";
  const scopeTitle = sandboxBackend
    ? `Dependencies are managed by the ${sandboxBackend} sandbox selected when marimo started.`
    : scopeLabel;

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      <InstallPackageForm context={dependencies.context} onSuccess={refetch} />
      {(isTreeSupported || isSandbox) && (
        <div className="flex items-center justify-between px-2 py-1 border-b">
          {isTreeSupported && !isSandbox ? (
            <div className="flex gap-1">
              <button
                type="button"
                className={cn(
                  "px-2 py-1 text-xs rounded",
                  viewMode === "list"
                    ? "bg-accent text-accent-foreground"
                    : "text-muted-foreground hover:text-foreground",
                )}
                onClick={() => setUserViewMode("list")}
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
                onClick={() => setUserViewMode("tree")}
              >
                Tree
              </button>
            </div>
          ) : (
            <div />
          )}
          <div className="flex items-center gap-2">
            <div
              className="items-center border px-2 py-0.5 text-xs transition-colors focus:outline-hidden focus:ring-2 focus:ring-ring focus:ring-offset-2 text-foreground rounded-sm text-ellipsis block overflow-hidden max-w-fit font-medium"
              title={scopeTitle}
            >
              {scopeLabel}
            </div>
            {name && !isSandbox && (
              <span className="text-xs text-muted-foreground">
                {name}
                {version && ` v${version}`}
              </span>
            )}
          </div>
        </div>
      )}
      {viewMode === "list" ? (
        <PackagesList packages={dependencies.list} onSuccess={refetch} />
      ) : (
        <DependencyTree
          tree={dependencies.tree}
          error={error}
          sandboxBackend={sandboxBackend}
          onSuccess={refetch}
        />
      )}
    </div>
  );
};

export default PackagesPanel;

const InstallPackageForm: React.FC<{
  context: PackageInstallationContext;
  onSuccess: () => void;
}> = ({ onSuccess, context }) => {
  const [input, setInput] = React.useState("");
  const { handleClick: openSettings } = useOpenSettingsToTab();
  const isSandbox = context.kind === "sandbox";
  const packageManager = isSandbox ? context.backend : context.name;

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

  const { loading, handleInstallPackages } = useInstallPackages();
  const onSuccessInstallPackages = () => {
    onSuccess();
    setInput("");
  };

  const installPackages = () => {
    const cleanedInput = stripPackageManagerPrefix(input);
    handleInstallPackages(
      [cleanedInput], // the backend will handle splitting the packages
      onSuccessInstallPackages,
    );
  };

  return (
    <div className="flex items-center w-full border-b">
      <SearchInput
        placeholder={
          isSandbox
            ? `Add packages to ${packageManager} sandbox...`
            : `Install packages with ${packageManager}...`
        }
        id={PACKAGES_INPUT_ID}
        icon={
          loading ? (
            <Spinner
              size="small"
              className="mr-2 h-4 w-4 shrink-0 opacity-50"
            />
          ) : isSandbox ? (
            <BoxIcon
              aria-hidden="true"
              className="mr-2 h-4 w-4 shrink-0 opacity-50"
            />
          ) : (
            <Tooltip
              content={`Change package manager (currently ${packageManager})`}
            >
              <button
                type="button"
                aria-label="Change package manager"
                onClick={() => openSettings("packageManagementAndData")}
                className="pointer-events-auto mr-2 rounded-sm opacity-50 hover:opacity-80 focus-visible:outline-hidden focus-visible:ring-1 focus-visible:ring-ring"
              >
                <BoxIcon aria-hidden="true" className="h-4 w-4 shrink-0" />
              </button>
            </Tooltip>
          )
        }
        rootClassName="flex-1 border-none"
        value={input}
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            e.preventDefault();
            installPackages();
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
            {isSandbox ? (
              <span>
                Packages are recorded in this notebook&apos;s inline metadata
                and synchronized with its {packageManager} sandbox. To switch
                backends, restart marimo with a different --sandbox option.
              </span>
            ) : (
              <span>
                Packages are installed using {packageManager}, selected in your
                user configuration.
              </span>
            )}
            <span className="mt-2">
              You can install packages with various formats:
            </span>
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
        onClick={installPackages}
        disabled={!input}
      >
        Add
      </button>
    </div>
  );
};

const PackagesList: React.FC<{
  onSuccess: () => void;
  packages: { name: string; version: string }[];
}> = ({ onSuccess, packages }) => {
  // Sort case-insensitively so packages are strictly alphabetical
  // regardless of capitalization (package managers sort inconsistently).
  const sortedPackages = React.useMemo(
    () =>
      packages.toSorted((a, b) =>
        a.name.localeCompare(b.name, undefined, { sensitivity: "base" }),
      ),
    [packages],
  );

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
        {sortedPackages.map((item) => (
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
  tags?: { kind: string; value: string }[];
  onSuccess: () => void;
}> = ({ packageName, tags, onSuccess }) => {
  const [loading, setLoading] = React.useState(false);
  const { addPackage } = useRequestClient();

  // Hide upgrade button in WASM
  if (isWasm()) {
    return null;
  }

  const handleUpgradePackage = async () => {
    try {
      setLoading(true);
      const group = tags?.find((tag) => tag.kind === "group")?.value;
      const response = await addPackage({
        package: packageName,
        upgrade: true,
        group,
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
  tags?: { kind: string; value: string }[];
  onSuccess: () => void;
}> = ({ packageName, tags, onSuccess }) => {
  const [loading, setLoading] = React.useState(false);
  const { removePackage } = useRequestClient();

  const handleRemovePackage = async () => {
    try {
      setLoading(true);
      const group = tags?.find((tag) => tag.kind === "group")?.value;
      const response = await removePackage({
        package: packageName,
        group,
      });
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
  tree: DependencyTreeNode | null;
  error?: Error | null;
  sandboxBackend: "uv" | "pixi" | null;
  onSuccess: () => void;
}> = ({ tree, error, sandboxBackend, onSuccess }) => {
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
    return (
      <PanelEmptyState
        title="Dependency tree unavailable"
        description="The sandbox did not return a dependency tree."
        icon={<BoxIcon />}
      />
    );
  }

  if (tree.dependencies.length === 0) {
    if (sandboxBackend === "pixi") {
      return (
        <PanelEmptyState
          title="No PyPI dependencies"
          description="Conda dependencies are not shown in this panel."
          icon={<BoxIcon />}
        />
      );
    }
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
          "hover:bg-(--slate-2) focus:bg-(--slate-2) focus:outline-hidden",
          hasChildren && "select-none",
          isTopLevel ? "px-2 py-0.5" : "",
        )}
        style={isTopLevel ? {} : { paddingLeft: `${indent}px` }}
        onClick={handleClick}
        onKeyDown={handleKeyDown}
        tabIndex={0}
        role="treeitem"
        aria-selected={false}
        aria-expanded={hasChildren ? isExpanded : undefined}
      >
        {/* Expand/collapse arrow */}
        {hasChildren ? (
          isExpanded ? (
            <ChevronDownIcon className="w-4 h-4 mr-2 shrink-0" />
          ) : (
            <ChevronRightIcon className="w-4 h-4 mr-2 shrink-0" />
          )
        ) : (
          <div className="w-4 mr-2 shrink-0" />
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
            if (tag.kind === "dedupe") {
              return (
                <div
                  key={index}
                  className="items-center border px-2 py-0.5 text-xs transition-colors focus:outline-hidden focus:ring-2 focus:ring-ring focus:ring-offset-2 text-muted-foreground rounded-sm text-ellipsis block overflow-hidden max-w-fit font-medium"
                  title="Package tree already displayed"
                >
                  already in tree
                </div>
              );
            }
            if (tag.kind === "cycle") {
              return (
                <div
                  key={index}
                  className="items-center border px-2 py-0.5 text-xs transition-colors focus:outline-hidden focus:ring-2 focus:ring-ring focus:ring-offset-2 text-foreground rounded-sm text-ellipsis block overflow-hidden max-w-fit font-medium border-orange-300 dark:border-orange-700 text-orange-700 dark:text-orange-300"
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
                  className="items-center border px-2 py-0.5 text-xs transition-colors focus:outline-hidden focus:ring-2 focus:ring-ring focus:ring-offset-2 text-foreground rounded-sm text-ellipsis block overflow-hidden max-w-fit font-medium border-blue-300 dark:border-blue-700 text-blue-700 dark:text-blue-300"
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
                  className="items-center border px-2 py-0.5 text-xs transition-colors focus:outline-hidden focus:ring-2 focus:ring-ring focus:ring-offset-2 text-foreground rounded-sm text-ellipsis block overflow-hidden max-w-fit font-medium border-green-300 dark:border-green-700 text-green-700 dark:text-green-300"
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
          <div className="flex gap-1 invisible group-hover:visible">
            <UpgradeButton
              packageName={node.name}
              tags={node.tags}
              onSuccess={onSuccess}
            />

            <RemoveButton
              packageName={node.name}
              tags={node.tags}
              onSuccess={onSuccess}
            />
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

function resolveViewMode(
  userViewMode: ViewMode | null,
  isTreeSupported: boolean,
): ViewMode {
  if (userViewMode === "list") {
    return "list";
  }
  if (isTreeSupported) {
    return userViewMode || "tree";
  }
  return "list";
}
