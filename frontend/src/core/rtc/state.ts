/* Copyright 2024 Marimo. All rights reserved. */
import { atomWithStorage } from "jotai/utils";

/**
 * The username for the current user when using real-time collaboration.
 * This is stored in localStorage.
 */
export const usernameAtom = atomWithStorage<string>("marimo:rtc:username", "");
