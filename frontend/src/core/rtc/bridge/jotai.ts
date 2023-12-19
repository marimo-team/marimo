/* Copyright 2023 Marimo. All rights reserved. */
import { PrimitiveAtom, createStore } from "jotai";

import { Doc as YDoc, transact } from "yjs";
import { patchYjs, toSharedType } from "./patchYjs";
import { isObject } from "lodash-es";

const ROOT_MAP_NAME = "root";

/**
 * Bind a yjs document to a jotai atom.
 * */
export const bind = <T, K extends keyof T & string>(
  yDoc: YDoc,
  store: ReturnType<typeof createStore>,
  atom: PrimitiveAtom<T>,
  syncedSlices: K[]
) => {
  // Set initial values from store, while preventing overriding remote states.
  const rootMap = yDoc.getMap(ROOT_MAP_NAME);
  const state = store.get(atom);
  if (isObject(state)) {
    transact(yDoc, () => {
      for (const sliceName of syncedSlices) {
        rootMap.set(sliceName, toSharedType({}));
        patchYjs(rootMap, sliceName, {}, state[sliceName]);
      }
    });
  } else {
    throw new Error("State must be an object.");
  }

  // Prevent reacting to our own changes.
  let currentlyPatchingYjs = false;
  let currentlyPatchingStore = false;

  // Connect yjs to jotai
  let currentState = store.get(atom);
  const jotaiUnsubscribe = store.sub(atom, () => {
    if (currentlyPatchingStore) {
      return;
    }

    const prevState = currentState;
    currentState = store.get(atom);

    currentlyPatchingYjs = true;
    transact(yDoc, () => {
      for (const sliceName of syncedSlices) {
        patchYjs(
          rootMap,
          sliceName,
          prevState[sliceName],
          currentState[sliceName]
        );
      }
    });
    currentlyPatchingYjs = false;
  });

  // Connect jotai to yjs
  const handleYjsStoreChange = () => {
    if (currentlyPatchingYjs) {
      return;
    }

    currentlyPatchingStore = true;
    // Set the value of the atom to the value of the yjs map.
    for (const sliceName of syncedSlices) {
      const value = rootMap.toJSON()[sliceName];
      store.set(atom, {
        ...store.get(atom),
        [sliceName]: value,
      });
    }
    currentlyPatchingStore = false;
  };

  rootMap.observeDeep(handleYjsStoreChange);

  return () => {
    jotaiUnsubscribe();
    rootMap.unobserveDeep(handleYjsStoreChange);
  };
};
