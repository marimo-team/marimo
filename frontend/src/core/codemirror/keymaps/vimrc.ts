/* Copyright 2024 Marimo. All rights reserved. */
export interface VimCommandSchema {
  mode?: VimMode;
  args?: string[];
}

export interface VimCommand {
  name: string;
  args?: VimCommandArgs;
  mode?: VimMode;
}

export interface VimCommandArgs {
  [key: string]: string;
}

export type VimMode = "normal" | "visual" | "insert";

export const KnownCommands: { [key: string]: VimCommandSchema } = {
  map: {
    args: ["lhs", "rhs"],
  },
  nmap: {
    mode: "normal",
    args: ["lhs", "rhs"],
  },
  vmap: {
    mode: "visual",
    args: ["lhs", "rhs"],
  },
  imap: {
    mode: "insert",
    args: ["lhs", "rhs"],
  },

  noremap: {
    args: ["lhs", "rhs"],
  },
  nnoremap: {
    mode: "normal",
    args: ["lhs", "rhs"],
  },
  vnoremap: {
    mode: "visual",
    args: ["lhs", "rhs"],
  },
  inoremap: {
    mode: "insert",
    args: ["lhs", "rhs"],
  },

  unmap: {
    args: ["lhs"],
  },
  nunmap: {
    mode: "normal",
    args: ["lhs"],
  },
  vunmap: {
    mode: "visual",
    args: ["lhs"],
  },
  iunmap: {
    mode: "insert",
    args: ["lhs"],
  },

  mapclear: {},
  nmapclear: {
    mode: "normal",
  },
  vmapclear: {
    mode: "visual",
  },
  imapclear: {
    mode: "insert",
  },
};

export type ParseError = (msg: string) => void;

/**
 * Parses a vimrc file into a list of mappings
 * Does not stop parsing when errors occur, instead just skips the faulty line
 *
 * @param content - The content of the vimrc file
 * @param parseError - Optional logger that gets called on parse errors
 * @returns A list of mappings
 */
export function parseVimrc(
  vimrc: string,
  parseError?: ParseError,
): VimCommand[] {
  const commands: VimCommand[] = [];

  for (const line of vimrc.split("\n")) {
    if (line.startsWith('"') || line.trim() === "") {
      continue;
    }
    const command = parseCommand(line, parseError);
    if (command) {
      commands.push(command);
    }
  }

  return commands;
}

function parseCommand(
  line: string,
  parseError?: ParseError,
): VimCommand | undefined {
  const words = line.split(/\s+/);

  const commandName = words[0];
  let currentWord = 0;

  if (commandName in KnownCommands) {
    const schema = KnownCommands[commandName];

    const args: VimCommandArgs = {};
    for (const argName of schema.args || []) {
      currentWord += 1;
      if (currentWord < words.length) {
        args[argName] = words[currentWord];
      } else {
        if (parseError) {
          parseError(
            `Not enough aruments for "${commandName}" command: "${line}"`,
          );
        }
        return;
      }
    }

    const command: VimCommand = { name: commandName };
    if ("args" in schema) {
      command.args = args;
    }
    if ("mode" in schema) {
      command.mode = schema.mode;
    }
    return command;
  }
  if (parseError) {
    parseError(`Unknown vimrc command: "${line}"`);
  }
  return;
}
