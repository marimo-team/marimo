/* Copyright 2023 Marimo. All rights reserved. */

// export function useCellEditor(opts: {
//   cellId: CellId;
//   prepareForRun: (opts: { cellId: CellId }) => void;
// }) {
//   const { cellId, prepareForRun } = opts;

//   const editorView = useRef<EditorView | null>(null);
//   const editorViewParentRef = useRef<HTMLDivElement>(null);
//   const runningOrQueuedRef = useRef<boolean | null>(null);

//   const { sendToTop, sendToBottom } = useCellActions();

//   // Hack to provide the value of `running` to Code Mirror's EditorView.
//   useEffect(() => {
//     runningOrQueuedRef.current = loading;
//   }, [loading]);

//   const onRun = useCallback(() => {
//     if (!runningOrQueuedRef.current) {
//       const code = prepareToRunEffects();
//       registerRunStart();
//       sendRun(cellId, code);
//     }
//   }, [cellId, registerRunStart, prepareToRunEffects]);

//   const createBelow = useCallback(
//     () => createNewCell({ cellId, before: false }),
//     [cellId, createNewCell]
//   );
//   const createAbove = useCallback(
//     () => createNewCell({ cellId, before: true }),
//     [cellId, createNewCell]
//   );
//   const moveDown = useCallback(
//     () => moveCell({ cellId, before: false }),
//     [cellId, moveCell]
//   );
//   const moveUp = useCallback(
//     () => moveCell({ cellId, before: true }),
//     [cellId, moveCell]
//   );
//   const focusDown = useCallback(
//     () => focusCell({ cellId, before: false }),
//     [cellId, focusCell]
//   );
//   const focusUp = useCallback(
//     () => focusCell({ cellId, before: true }),
//     [cellId, focusCell]
//   );

//   useEffect(() => {
//     if (reading) {
//       return;
//     }

//     const deleteCellIfNotRunning = () => {
//       // Cannot delete running cells, since we're waiting for their output.
//       if (!runningOrQueuedRef.current) {
//         deleteCell({ cellId });
//         return true;
//       }
//       return false;
//     };

//     const extensions = setupCodeMirror({
//       cellId,
//       showPlaceholder,
//       cellCodeCallbacks: {
//         updateCellCode,
//       },
//       cellMovementCallbacks: {
//         onRun,
//         deleteCell: deleteCellIfNotRunning,
//         createAbove,
//         createBelow,
//         moveUp,
//         moveDown,
//         focusUp,
//         focusDown,
//         sendToTop,
//         sendToBottom,
//         moveToNextCell,
//       },
//       completionConfig: userConfig.completion,
//       keymapConfig: userConfig.keymap,
//       theme,
//     });

//     // Should focus will be true if its a newly created editor
//     let shouldFocus: boolean;
//     if (serializedEditorState === null) {
//       // If the editor already exists, reconfigure it with the new extensions.
//       // Triggered when, e.g., placeholder changes.
//       if (editorView.current === null) {
//         // Otherwise, create a new editor.
//         editorView.current = new EditorView({
//           state: EditorState.create({
//             doc: initialContents,
//             extensions: extensions,
//           }),
//         });
//         shouldFocus = true;
//       } else {
//         editorView.current.dispatch({
//           effects: [StateEffect.reconfigure.of([extensions])],
//         });
//         shouldFocus = false;
//       }
//     } else {
//       editorView.current = new EditorView({
//         state: EditorState.fromJSON(
//           serializedEditorState,
//           {
//             doc: initialContents,
//             extensions: extensions,
//           },
//           { history: historyField }
//         ),
//       });
//       shouldFocus = true;
//     }

//     if (editorView.current !== null && editorViewParentRef.current !== null) {
//       // Always replace the children in case the editor view was re-created.
//       editorViewParentRef.current.replaceChildren(editorView.current.dom);
//     }

//     if (shouldFocus && allowFocus) {
//       // Focus and scroll into view; request an animation frame to
//       // avoid a race condition when new editors are created
//       // very rapidly by holding a hotkey
//       requestAnimationFrame(() => {
//         editorView.current?.focus();
//         editorView.current?.dom.scrollIntoView({
//           behavior: "smooth",
//           block: "center",
//         });
//       });
//     }

//     // We don't want to re-run this effect when `allowFocus` changes.
//     // eslint-disable-next-line react-hooks/exhaustive-deps
//   }, [
//     reading,
//     cellId,
//     userConfig.completion.activate_on_typing,
//     userConfig.keymap,
//     theme,
//     showPlaceholder,
//     initialContents,
//     createAbove,
//     createBelow,
//     deleteCell,
//     focusUp,
//     focusDown,
//     moveUp,
//     moveDown,
//     moveToNextCell,
//     updateCellCode,
//     onRun,
//     serializedEditorState,
//   ]);

//   useLayoutEffect(() => {
//     if (editorView.current === null) {
//       return;
//     }
//     if (
//       editing &&
//       editorViewParentRef.current !== null &&
//       editorView.current !== null
//     ) {
//       editorViewParentRef.current.replaceChildren(editorView.current.dom);
//     }
//   }, [editing]);
// }
