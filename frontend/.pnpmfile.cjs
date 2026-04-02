// oxlint-disable typescript/no-dynamic-delete
const IGNORE = ["vue", "solid-js", "svelte", "solid-swr-store"];

module.exports = {
  hooks: {
    readPackage: (pkg) => {
      for (const key of IGNORE) {
        delete pkg.peerDependencies[key];
        delete pkg.dependencies[key];
      }
      return pkg;
    },
  },
};
