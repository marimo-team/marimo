/* Copyright 2024 Marimo. All rights reserved. */
import { describe, expect, test } from "vitest";
import {
  AnsiParser,
  AnsiReducer,
  StatefulOutputMessage,
  TerminalBuffer,
} from "../ansi-reduce";

describe("TerminalBuffer", () => {
  test("writeChar writes single character", () => {
    const buffer = new TerminalBuffer();
    buffer.writeChar("a");
    expect(buffer.render()).toMatchInlineSnapshot(`"a"`);
  });

  test("writeChar writes multiple characters", () => {
    const buffer = new TerminalBuffer();
    buffer.writeChar("H");
    buffer.writeChar("e");
    buffer.writeChar("l");
    buffer.writeChar("l");
    buffer.writeChar("o");
    expect(buffer.render()).toMatchInlineSnapshot(`"Hello"`);
  });

  test("writeChar overwrites at cursor position", () => {
    const buffer = new TerminalBuffer();
    buffer.writeChar("a");
    buffer.writeChar("b");
    buffer.writeChar("c");
    // Move cursor back and overwrite
    buffer.handleEscape("\u001B[2D"); // Move left 2
    buffer.writeChar("X");
    buffer.writeChar("Y");
    expect(buffer.render()).toMatchInlineSnapshot(`"aXY"`);
  });

  test("control handles newline", () => {
    const buffer = new TerminalBuffer();
    buffer.writeChar("a");
    buffer.control("\n");
    buffer.writeChar("b");
    expect(buffer.render()).toMatchInlineSnapshot(`
      "a
      b"
    `);
  });

  test("control handles tab", () => {
    const buffer = new TerminalBuffer();
    buffer.writeChar("a");
    buffer.control("\t");
    buffer.writeChar("b");
    expect(buffer.render()).toMatchInlineSnapshot(`"a	b"`);
  });

  test("control handles carriage return", () => {
    const buffer = new TerminalBuffer();
    buffer.writeChar("a");
    buffer.writeChar("b");
    buffer.writeChar("c");
    buffer.control("\r");
    buffer.writeChar("X");
    buffer.writeChar("Y");
    expect(buffer.render()).toMatchInlineSnapshot(`"XYc"`);
  });

  test("handleEscape cursor up", () => {
    const buffer = new TerminalBuffer();
    buffer.writeChar("a");
    buffer.control("\n");
    buffer.writeChar("b");
    buffer.handleEscape("\u001B[1A"); // Move up 1
    buffer.writeChar("X");
    expect(buffer.render()).toMatchInlineSnapshot(`"aX"`);
  });

  test("handleEscape cursor down", () => {
    const buffer = new TerminalBuffer();
    buffer.writeChar("a");
    buffer.handleEscape("\u001B[1B"); // Move down 1
    buffer.writeChar("b");
    expect(buffer.render()).toMatchInlineSnapshot(`
      "a
       b"
    `);
  });

  test("handleEscape cursor forward", () => {
    const buffer = new TerminalBuffer();
    buffer.writeChar("a");
    buffer.handleEscape("\u001B[3C"); // Move right 3
    buffer.writeChar("b");
    expect(buffer.render()).toMatchInlineSnapshot(`"a   b"`);
  });

  test("handleEscape cursor back", () => {
    const buffer = new TerminalBuffer();
    buffer.writeChar("a");
    buffer.writeChar("b");
    buffer.writeChar("c");
    buffer.handleEscape("\u001B[2D"); // Move left 2
    buffer.writeChar("X");
    expect(buffer.render()).toMatchInlineSnapshot(`"aXc"`);
  });

  test("handleEscape cursor home with params", () => {
    const buffer = new TerminalBuffer();
    buffer.writeChar("a");
    buffer.control("\n");
    buffer.writeChar("b");
    buffer.handleEscape("\u001B[1;1H"); // Move to (1,1) which is (0,0) in 0-indexed
    buffer.writeChar("X");
    expect(buffer.render()).toMatchInlineSnapshot(`
      "X
      b"
    `);
  });

  test("handleEscape cursor home without params", () => {
    const buffer = new TerminalBuffer();
    buffer.writeChar("a");
    buffer.writeChar("b");
    buffer.handleEscape("\u001B[H"); // Move to home
    buffer.writeChar("X");
    expect(buffer.render()).toMatchInlineSnapshot(`"Xb"`);
  });

  test("handleEscape erase display (2J)", () => {
    const buffer = new TerminalBuffer();
    buffer.writeChar("a");
    buffer.control("\n");
    buffer.writeChar("b");
    buffer.handleEscape("\u001B[2J"); // Clear screen
    buffer.writeChar("X");
    expect(buffer.render()).toMatchInlineSnapshot(`"X"`);
  });

  test("handleEscape erase line to end (0K)", () => {
    const buffer = new TerminalBuffer();
    buffer.writeChar("a");
    buffer.writeChar("b");
    buffer.writeChar("c");
    buffer.handleEscape("\u001B[2D"); // Move left 2
    buffer.handleEscape("\u001B[0K"); // Clear to end
    expect(buffer.render()).toMatchInlineSnapshot(`"a"`);
  });

  test("handleEscape erase line to start (1K)", () => {
    const buffer = new TerminalBuffer();
    buffer.writeChar("a");
    buffer.writeChar("b");
    buffer.writeChar("c");
    buffer.handleEscape("\u001B[2D"); // Move left 2
    buffer.handleEscape("\u001B[1K"); // Clear to start
    expect(buffer.render()).toMatchInlineSnapshot(`" bc"`);
  });

  test("handleEscape erase entire line (2K)", () => {
    const buffer = new TerminalBuffer();
    buffer.writeChar("a");
    buffer.writeChar("b");
    buffer.writeChar("c");
    buffer.handleEscape("\u001B[2K"); // Clear entire line
    expect(buffer.render()).toMatchInlineSnapshot(`""`);
  });
});

describe("AnsiParser", () => {
  test("parse plain text", () => {
    const parser = new AnsiParser();
    const tokens = parser.parse("hello");
    expect(tokens).toMatchInlineSnapshot(`
      [
        {
          "type": "text",
          "value": "hello",
        },
      ]
    `);
  });

  test("parse text with escape sequence", () => {
    const parser = new AnsiParser();
    const tokens = parser.parse("hello\u001B[1Aworld");
    expect(tokens).toMatchInlineSnapshot(`
      [
        {
          "type": "text",
          "value": "hello",
        },
        {
          "type": "escape",
          "value": "[1A",
        },
        {
          "type": "text",
          "value": "world",
        },
      ]
    `);
  });

  test("parse multiple escape sequences", () => {
    const parser = new AnsiParser();
    const tokens = parser.parse("\u001B[1A\u001B[2C\u001B[0K");
    expect(tokens).toMatchInlineSnapshot(`
      [
        {
          "type": "escape",
          "value": "[1A",
        },
        {
          "type": "escape",
          "value": "[2C",
        },
        {
          "type": "escape",
          "value": "[0K",
        },
      ]
    `);
  });

  test("parse escape with multiple parameters", () => {
    const parser = new AnsiParser();
    const tokens = parser.parse("\u001B[10;20H");
    expect(tokens).toMatchInlineSnapshot(`
      [
        {
          "type": "escape",
          "value": "[10;20H",
        },
      ]
    `);
  });

  test("parse empty string", () => {
    const parser = new AnsiParser();
    const tokens = parser.parse("");
    expect(tokens).toMatchInlineSnapshot("[]");
  });
});

describe("AnsiReducer", () => {
  test("reduce plain text", () => {
    const reducer = new AnsiReducer();
    const result = reducer.reduce("hello world");
    expect(result).toMatchInlineSnapshot(`"hello world"`);
  });

  test("reduce text with newlines", () => {
    const reducer = new AnsiReducer();
    const result = reducer.reduce("line1\nline2\nline3");
    expect(result).toMatchInlineSnapshot(`
      "line1
      line2
      line3"
    `);
  });

  test("reduce progress bar simulation", () => {
    const reducer = new AnsiReducer();
    const result = reducer.reduce(
      "Progress: 10%\rProgress: 50%\rProgress: 100%",
    );
    expect(result).toMatchInlineSnapshot(`"Progress: 100%"`);
  });

  test("reduce spinner simulation", () => {
    const reducer = new AnsiReducer();
    const result = reducer.reduce(
      "Loading |\rLoading /\rLoading -\rLoading \\",
    );
    expect(result).toMatchInlineSnapshot(`"Loading \\"`);
  });

  test("reduce cursor movement", () => {
    const reducer = new AnsiReducer();
    const result = reducer.reduce("Hello\u001B[5DWorld");
    expect(result).toMatchInlineSnapshot(`"World"`);
  });

  test("reduce clear line", () => {
    const reducer = new AnsiReducer();
    const result = reducer.reduce("Hello World\u001B[2K");
    expect(result).toMatchInlineSnapshot(`""`);
  });

  test("reduce clear screen", () => {
    const reducer = new AnsiReducer();
    const result = reducer.reduce("Line 1\nLine 2\n\u001B[2JNew Start");
    expect(result).toMatchInlineSnapshot(`"New Start"`);
  });

  test("reduce complex cursor positioning", () => {
    const reducer = new AnsiReducer();
    const result = reducer.reduce("abc\u001B[1;2Hxy");
    expect(result).toMatchInlineSnapshot(`"axy"`);
  });

  test("reduce ignores control characters below space", () => {
    const reducer = new AnsiReducer();
    const result = reducer.reduce("hello\u0000\u0001\u0007world");
    expect(result).toMatchInlineSnapshot(`"helloworld"`);
  });

  test("reduce handles carriage return without newline", () => {
    const reducer = new AnsiReducer();
    const result = reducer.reduce("AAAA\rBB");
    expect(result).toMatchInlineSnapshot(`"BBAA"`);
  });
});

function ansiReduce(input: string): string {
  const reducer = new AnsiReducer();
  return reducer.reduce(input);
}

describe("ansiReduce", () => {
  test("basic usage", () => {
    const result = ansiReduce("Hello World");
    expect(result).toMatchInlineSnapshot(`"Hello World"`);
  });

  test("progress bar example", () => {
    const result = ansiReduce(
      "[          ] 0%\r[==        ] 20%\r[====      ] 40%\r[======    ] 60%\r[========  ] 80%\r[==========] 100%",
    );
    expect(result).toMatchInlineSnapshot(`"[==========] 100%"`);
  });

  test("multi-line with cursor movement", () => {
    const result = ansiReduce("Line 1\nLine 2\nLine 3\u001B[2AModified");
    expect(result).toMatchInlineSnapshot(`"Line 1Modified"`);
  });

  test("erase and rewrite", () => {
    const result = ansiReduce("Old text\u001B[2KNew text");
    expect(result).toMatchInlineSnapshot(`"        New text"`);
  });

  test("empty input", () => {
    const result = ansiReduce("");
    expect(result).toMatchInlineSnapshot(`""`);
  });

  test("newlines only", () => {
    const result = ansiReduce("\n\n\n");
    expect(result).toMatchInlineSnapshot(`
      "


      "
    `);
  });

  test("real-world tqdm-like progress", () => {
    const result = ansiReduce(
      "Processing: |          | 0/100\r" +
        "Processing: |█         | 10/100\r" +
        "Processing: |██        | 20/100\r" +
        "Processing: |██████████| 100/100",
    );
    expect(result).toMatchInlineSnapshot(`"Processing: |██████████| 100/100"`);
  });

  test("cursor positioning with absolute coordinates", () => {
    const result = ansiReduce("\u001B[1;1Ha\u001B[2;2Hb\u001B[3;3Hc");
    expect(result).toMatchInlineSnapshot(`
      "a
       b
        c"
    `);
  });

  test("partial line erase from cursor to end", () => {
    const result = ansiReduce("Hello World\u001B[6D\u001B[0K!");
    expect(result).toMatchInlineSnapshot(`"Hello!"`);
  });

  test("partial line erase from start to cursor", () => {
    const result = ansiReduce("Hello World\u001B[6D\u001B[1K!");
    expect(result).toMatchInlineSnapshot(`"     !World"`);
  });

  test("complex progress simulation", () => {
    const text =
      "\r  0%|                                                              | 0/101000 [00:00<?, ?it/s]\rCompiling.. :   0%|                                                | 0/101000 [00:00<?, ?it/s]\n\r  0%|                                                              | 0/101000 [00:00<?, ?it/s]\u001B[A\n\rCompiling.. :   0%|                                                | 0/101000 [00:00<?, ?it/s]\u001B[A\n\n\r  0%|                                                              | 0/101000 [00:00<?, ?it/s]\u001B[A\u001B[A\n\n\rCompiling.. :   0%|                                                | 0/101000 [00:00<?, ?it/s]\u001B[A\u001B[A\n\n\n\r ... (more hidden) ...\u001B[A\u001B[A\u001B[A\n\n\n\r ... (more hidden) ...\u001B[A\u001B[A\u001B[A\rRunning chain 0:   0%|                                             | 0/101000 [00:00<?, ?it/s]\n\rRunning chain 1:   0%|                                             | 0/101000 [00:00<?, ?it/s]\u001B[A\n\n\rRunning chain 2:   0%|                                             | 0/101000 [00:00<?, ?it/s]\u001B[A\u001B[A\n\n\n\r ... (more hidden) ...\u001B[A\u001B[A\u001B[A\n\n\n\r ... (more hidden) ...\u001B[A\u001B[A\u001B[A\n\n\rRunning chain 2:  15%|████▎                        | 15150/101000 [00:00<00:00, 129479.68it/s]\u001B[A\u001B[A\n\rRunning chain 1:  15%|████▎                        | 15150/101000 [00:00<00:00, 124469.08it/s]\u001B[A\rRunning chain 0:  15%|████▎                        | 15150/101000 [00:00<00:00, 122865.03it/s]\n\n\n\r ... (more hidden) ...\u001B[A\u001B[A\u001B[A\n\n\rRunning chain 2:  30%|████████▋                    | 30300/101000 [00:00<00:00, 130679.02it/s]\u001B[A\u001B[A\n\rRunning chain 1:  30%|████████▋                    | 30300/101000 [00:00<00:00, 126103.71it/s]\u001B[A\rRunning chain 0:  30%|████████▋                    | 30300/101000 [00:00<00:00, 124748.00it/s]\n\n\n\r ... (more hidden) ...\u001B[A\u001B[A\u001B[A\n\n\rRunning chain 2:  45%|█████████████                | 45450/101000 [00:00<00:00, 127078.72it/s]\u001B[A\u001B[A\n\rRunning chain 1:  45%|█████████████                | 45450/101000 [00:00<00:00, 123708.59it/s]\u001B[A\rRunning chain 0:  45%|█████████████                | 45450/101000 [00:00<00:00, 121550.69it/s]\n\n\n\r ... (more hidden) ...\u001B[A\u001B[A\u001B[A\n\n\rRunning chain 2:  60%|█████████████████▍           | 60600/101000 [00:00<00:00, 126319.28it/s]\u001B[A\u001B[A\n\rRunning chain 1:  60%|█████████████████▍           | 60600/101000 [00:00<00:00, 123669.56it/s]\u001B[A\rRunning chain 0:  60%|█████████████████▍           | 60600/101000 [00:00<00:00, 122438.92it/s]\n\n\n\r ... (more hidden) ...\u001B[A\u001B[A\u001B[A\n\n\rRunning chain 2:  75%|█████████████████████▊       | 75750/101000 [00:00<00:00, 126984.84it/s]\u001B[A\u001B[A\n\rRunning chain 1:  75%|█████████████████████▊       | 75750/101000 [00:00<00:00, 123764.98it/s]\u001B[A\rRunning chain 0:  75%|█████████████████████▊       | 75750/101000 [00:00<00:00, 123796.97it/s]\n\n\n\r ... (more hidden) ...\u001B[A\u001B[A\u001B[A\n\n\rRunning chain 2:  90%|██████████████████████████   | 90900/101000 [00:01<00:00, 128241.91it/s]\u001B[A\u001B[A\n\rRunning chain 1:  90%|██████████████████████████   | 90900/101000 [00:01<00:00, 125149.55it/s]\u001B[A\rRunning chain 0:  90%|██████████████████████████   | 90900/101000 [00:01<00:00, 124582.89it/s]\rRunning chain 3: 100%|█████████████████████████████| 101000/101000 [00:01<00:00, 88054.93it/s]\n\rRunning chain 2: 100%|█████████████████████████████| 101000/101000 [00:01<00:00, 86530.93it/s]\n\rRunning chain 1: 100%|█████████████████████████████| 101000/101000 [00:01<00:00, 85142.19it/s]\n\rRunning chain 0: 100%|█████████████████████████████| 101000/101000 [00:01<00:00, 84719.76it/s]\n";
    expect(ansiReduce(text)).toMatchInlineSnapshot(`
      "Running chain 3: 100%|█████████████████████████████| 101000/101000 [00:01<00:00, 88054.93it/s]
      Running chain 2: 100%|█████████████████████████████| 101000/101000 [00:01<00:00, 86530.93it/s]
      Running chain 1: 100%|█████████████████████████████| 101000/101000 [00:01<00:00, 85142.19it/s]
      Running chain 0: 100%|█████████████████████████████| 101000/101000 [00:01<00:00, 84719.76it/s]
      "
    `);
  });

  test("more complex cursor movements", () => {
    const text =
      "\r  0%|                                                              | 0/101000 [00:00<?, ?it/s]\rCompiling.. :   0%|                                                | 0/101000 [00:00<?, ?it/s]\n\r  0%|                                                              | 0/101000 [00:00<?, ?it/s]\u001B[A\n\rCompiling.. :   0%|                                                | 0/101000 [00:00<?, ?it/s]\u001B[A\n\n\r  0%|                                                              | 0/101000 [00:00<?, ?it/s]\u001B[A\u001B[A\n\n\rCompiling.. :   0%|                                                | 0/101000 [00:00<?, ?it/s]\u001B[A\u001B[A\n\n\n\r ... (more hidden) ...\u001B[A\u001B[A\u001B[A\n\n\n\r ... (more hidden) ...\u001B[A\u001B[A\u001B[A\rRunning chain 0:   0%|                                             | 0/101000 [00:00<?, ?it/s]\n\rRunning chain 1:   0%|                                             | 0/101000 [00:00<?, ?it/s]\u001B[A\n\n\rRunning chain 2:   0%|                                             | 0/101000 [00:00<?, ?it/s]\u001B[A\u001B[A\n\n\n\r ... (more hidden) ...\u001B[A\u001B[A\u001B[A\n\n\n\r ... (more hidden) ...\u001B[A\u001B[A\u001B[A\n\n\n\r ... (more hidden) ...\u001B[A\u001B[A\u001B[A\n\n\n\r ... (more hidden) ...\u001B[A\u001B[A\u001B[A\rRunning chain 0:   5%|█▌                             | 5050/101000 [00:00<00:08, 11945.37it/s]\n\rRunning chain 1:   5%|█▌                             | 5050/101000 [00:00<00:08, 11535.69it/s]\u001B[A\n\n\rRunning chain 2:   5%|█▌                             | 5050/101000 [00:00<00:08, 11491.43it/s]\u001B[A\u001B[A\n\n\n\r ... (more hidden) ...\u001B[A\u001B[A\u001B[A\n\n\n\r ... (more hidden) ...\u001B[A\u001B[A\u001B[A\n\n\n\r ... (more hidden) ...\u001B[A\u001B[A\u001B[A\rRunning chain 0:  10%|███                           | 10100/101000 [00:01<00:07, 12010.48it/s]\rRunning chain 3: 100%|█████████████████████████████| 101000/101000 [00:01<00:00, 83919.80it/s]\n\n\rRunning chain 1:  10%|███                           | 10100/101000 [00:01<00:07, 11604.98it/s]\u001B[A\n\n\rRunning chain 2:  10%|███                           | 10100/101000 [00:01<00:07, 11575.75it/s]\u001B[A\u001B[A\rRunning chain 0:  15%|████▌                         | 15150/101000 [00:01<00:06, 12551.29it/s]\n\rRunning chain 1:  15%|████▌                         | 15150/101000 [00:01<00:07, 12082.69it/s]\u001B[A\n\n\rRunning chain 2:  15%|████▌                         | 15150/101000 [00:01<00:07, 12024.20it/s]\u001B[A\u001B[A\rRunning chain 0:  20%|██████                        | 20200/101000 [00:01<00:06, 12896.22it/s]\n\rRunning chain 1:  20%|██████                        | 20200/101000 [00:02<00:06, 12358.86it/s]\u001B[A\n\n\rRunning chain 2:  20%|██████                        | 20200/101000 [00:02<00:06, 12331.67it/s]\u001B[A\u001B[A\rRunning chain 0:  25%|███████▌                      | 25250/101000 [00:02<00:05, 12987.27it/s]\n\rRunning chain 1:  25%|███████▌                      | 25250/101000 [00:02<00:06, 12486.00it/s]\u001B[A\n\n\rRunning chain 2:  25%|███████▌                      | 25250/101000 [00:02<00:06, 12446.08it/s]\u001B[A\u001B[A\rRunning chain 0:  30%|█████████                     | 30300/101000 [00:02<00:05, 13286.93it/s]\n\rRunning chain 1:  30%|█████████                     | 30300/101000 [00:02<00:05, 12504.21it/s]\u001B[A\n\n\rRunning chain 2:  30%|█████████                     | 30300/101000 [00:02<00:05, 12362.40it/s]\u001B[A\u001B[A\rRunning chain 0:  35%|██████████▌                   | 35350/101000 [00:03<00:04, 13319.74it/s]\n\rRunning chain 1:  35%|██████████▌                   | 35350/101000 [00:03<00:05, 12636.28it/s]\u001B[A\n\n\rRunning chain 2:  35%|██████████▌                   | 35350/101000 [00:03<00:05, 12506.56it/s]\u001B[A\u001B[A\rRunning chain 0:  40%|████████████                  | 40400/101000 [00:03<00:04, 13473.33it/s]\n\rRunning chain 1:  40%|████████████                  | 40400/101000 [00:03<00:04, 12846.16it/s]\u001B[A\n\n\rRunning chain 2:  40%|████████████                  | 40400/101000 [00:03<00:04, 12683.84it/s]\u001B[A\u001B[A\rRunning chain 0:  45%|█████████████▌                | 45450/101000 [00:03<00:04, 13461.17it/s]\n\rRunning chain 1:  45%|█████████████▌                | 45450/101000 [00:03<00:04, 12862.53it/s]\u001B[A\n\n\rRunning chain 2:  45%|█████████████▌                | 45450/101000 [00:04<00:04, 12725.95it/s]\u001B[A\u001B[A\rRunning chain 0:  50%|███████████████               | 50500/101000 [00:04<00:03, 13487.23it/s]\n\rRunning chain 1:  50%|███████████████               | 50500/101000 [00:04<00:03, 12913.94it/s]\u001B[A\n\n\rRunning chain 2:  50%|███████████████               | 50500/101000 [00:04<00:03, 12775.79it/s]\u001B[A\u001B[A\rRunning chain 0:  55%|████████████████▌             | 55550/101000 [00:04<00:03, 13532.41it/s]\n\rRunning chain 1:  55%|████████████████▌             | 55550/101000 [00:04<00:03, 12942.85it/s]\u001B[A\n\n\rRunning chain 2:  55%|████████████████▌             | 55550/101000 [00:04<00:03, 12817.21it/s]\u001B[A\u001B[A\rRunning chain 0:  60%|██████████████████            | 60600/101000 [00:04<00:02, 13553.39it/s]\n\rRunning chain 1:  60%|██████████████████            | 60600/101000 [00:05<00:03, 12997.63it/s]\u001B[A\n\n\rRunning chain 2:  60%|██████████████████            | 60600/101000 [00:05<00:03, 12847.11it/s]\u001B[A\u001B[A\rRunning chain 0:  65%|███████████████████▌          | 65650/101000 [00:05<00:02, 13525.88it/s]\n\rRunning chain 1:  65%|███████████████████▌          | 65650/101000 [00:05<00:02, 12983.99it/s]\u001B[A\n\n\rRunning chain 2:  65%|███████████████████▌          | 65650/101000 [00:05<00:02, 12824.49it/s]\u001B[A\u001B[A\rRunning chain 0:  70%|█████████████████████         | 70700/101000 [00:05<00:02, 13491.28it/s]\n\rRunning chain 1:  70%|█████████████████████         | 70700/101000 [00:05<00:02, 13011.52it/s]\u001B[A\n\n\rRunning chain 2:  70%|█████████████████████         | 70700/101000 [00:05<00:02, 12779.17it/s]\u001B[A\u001B[A\rRunning chain 0:  75%|██████████████████████▌       | 75750/101000 [00:06<00:01, 13469.35it/s]\n\rRunning chain 1:  75%|██████████████████████▌       | 75750/101000 [00:06<00:01, 12989.82it/s]\u001B[A\n\n\rRunning chain 2:  75%|██████████████████████▌       | 75750/101000 [00:06<00:01, 12747.26it/s]\u001B[A\u001B[A\rRunning chain 0:  80%|████████████████████████      | 80800/101000 [00:06<00:01, 13449.38it/s]\n\rRunning chain 1:  80%|████████████████████████      | 80800/101000 [00:06<00:01, 12991.59it/s]\u001B[A\n\n\rRunning chain 2:  80%|████████████████████████      | 80800/101000 [00:06<00:01, 12750.35it/s]\u001B[A\u001B[A\rRunning chain 0:  85%|█████████████████████████▌    | 85850/101000 [00:06<00:01, 13411.69it/s]\n\rRunning chain 1:  85%|█████████████████████████▌    | 85850/101000 [00:07<00:01, 13116.35it/s]\u001B[A\n\n\rRunning chain 2:  85%|█████████████████████████▌    | 85850/101000 [00:07<00:01, 12779.54it/s]\u001B[A\u001B[A\rRunning chain 0:  90%|███████████████████████████   | 90900/101000 [00:07<00:00, 13610.86it/s]\n\rRunning chain 1:  90%|███████████████████████████   | 90900/101000 [00:07<00:00, 13109.18it/s]\u001B[A\rRunning chain 0:  95%|████████████████████████████▌ | 95950/101000 [00:07<00:00, 13590.91it/s]\n\n\rRunning chain 2:  90%|███████████████████████████   | 90900/101000 [00:07<00:00, 12786.82it/s]\u001B[A\u001B[A\n\rRunning chain 1:  95%|████████████████████████████▌ | 95950/101000 [00:07<00:00, 13082.02it/s]\u001B[A\rRunning chain 0: 100%|█████████████████████████████| 101000/101000 [00:07<00:00, 13573.97it/s]\rRunning chain 0: 100%|█████████████████████████████| 101000/101000 [00:07<00:00, 12749.04it/s]\n\n\n\rRunning chain 2:  95%|████████████████████████████▌ | 95950/101000 [00:07<00:00, 12922.54it/s]\u001B[A\u001B[A\n\rRunning chain 1: 100%|█████████████████████████████| 101000/101000 [00:08<00:00, 14371.12it/s]\u001B[A\rRunning chain 1: 100%|█████████████████████████████| 101000/101000 [00:08<00:00, 12442.67it/s]\n\n\n\rRunning chain 2: 100%|█████████████████████████████| 101000/101000 [00:08<00:00, 14869.01it/s]\u001B[A\u001B[A\rRunning chain 2: 100%|█████████████████████████████| 101000/101000 [00:08<00:00, 12373.90it/s]\n";
    const result = ansiReduce(text);
    expect(result).toMatchInlineSnapshot(`
      "Running chain 3: 100%|█████████████████████████████| 101000/101000 [00:01<00:00, 83919.80it/s]
      Running chain 0: 100%|█████████████████████████████| 101000/101000 [00:07<00:00, 12749.04it/s]
      Running chain 1: 100%|█████████████████████████████| 101000/101000 [00:08<00:00, 12442.67it/s]
      Running chain 2: 100%|█████████████████████████████| 101000/101000 [00:08<00:00, 12373.90it/s]
      "
    `);
  });
});

describe("AnsiReducer streaming with append()", () => {
  test("append simple text incrementally", () => {
    const reducer = new AnsiReducer();
    reducer.append("Hello ");
    reducer.append("World");
    expect(reducer.render()).toMatchInlineSnapshot(`"Hello World"`);
  });

  test("append with progress bar simulation", () => {
    const reducer = new AnsiReducer();
    reducer.append("Progress: 0%");
    reducer.append("\rProgress: 50%");
    reducer.append("\rProgress: 100%");
    expect(reducer.render()).toMatchInlineSnapshot(`"Progress: 100%"`);
  });

  test("append with newlines", () => {
    const reducer = new AnsiReducer();
    reducer.append("Line 1\n");
    reducer.append("Line 2\n");
    reducer.append("Line 3");
    expect(reducer.render()).toMatchInlineSnapshot(`
      "Line 1
      Line 2
      Line 3"
    `);
  });

  test("append with cursor movements", () => {
    const reducer = new AnsiReducer();
    reducer.append("abc\n");
    reducer.append("def\n");
    reducer.append("\u001B[1A"); // Move up one line
    reducer.append("XYZ");
    expect(reducer.render()).toMatchInlineSnapshot(`
      "abc
      XYZ"
    `);
  });

  test("reset clears state", () => {
    const reducer = new AnsiReducer();
    reducer.append("Old content");
    expect(reducer.render()).toMatchInlineSnapshot(`"Old content"`);

    reducer.reset();
    reducer.append("New content");
    expect(reducer.render()).toMatchInlineSnapshot(`"New content"`);
  });

  test("reduce() resets before processing", () => {
    const reducer = new AnsiReducer();
    reducer.append("Old content");
    const result = reducer.reduce("New content");
    expect(result).toMatchInlineSnapshot(`"New content"`);
  });

  test("streaming tqdm-like progress", () => {
    const reducer = new AnsiReducer();

    // Simulate streaming progress updates
    reducer.append("Processing: |          | 0/100\r");
    reducer.append("Processing: |██        | 20/100\r");
    reducer.append("Processing: |████      | 40/100\r");
    reducer.append("Processing: |██████    | 60/100\r");
    reducer.append("Processing: |████████  | 80/100\r");
    reducer.append("Processing: |██████████| 100/100");

    expect(reducer.render()).toMatchInlineSnapshot(
      `"Processing: |██████████| 100/100"`,
    );
  });

  test("append empty string does nothing", () => {
    const reducer = new AnsiReducer();
    reducer.append("Hello");
    reducer.append("");
    expect(reducer.render()).toMatchInlineSnapshot(`"Hello"`);
  });

  test("append with mixed content and escapes", () => {
    const reducer = new AnsiReducer();
    reducer.append("Loading");
    reducer.append(" |");
    reducer.append("\rLoading /");
    reducer.append("\rLoading -");
    reducer.append("\rLoading \\");
    reducer.append("\rDone!     ");
    expect(reducer.render()).toMatchInlineSnapshot(`"Done!     "`);
  });
});

describe("StatefulOutputMessage", () => {
  test("initializes and processes text", () => {
    const message = {
      mimetype: "text/plain",
      channel: "stdout",
      timestamp: 123,
      data: "Hello",
    } as const;
    const stateful = StatefulOutputMessage.create(message);

    expect(stateful.mimetype).toBe("text/plain");
    expect(stateful.channel).toBe("stdout");
    expect(stateful.data).toBe("Hello");
  });

  test("appendData appends text", () => {
    const message = {
      mimetype: "text/plain",
      channel: "stdout",
      timestamp: 0,
      data: "Hello",
    } as const;
    let stateful = StatefulOutputMessage.create(message);

    stateful = stateful.appendData(" World");

    expect(stateful.data).toBe("Hello World");
  });

  test("appendData handles progress bars", () => {
    const message = {
      mimetype: "text/plain",
      channel: "stdout",
      timestamp: 0,
      data: "Progress: 0%",
    } as const;
    let stateful = StatefulOutputMessage.create(message);

    stateful = stateful.appendData("\rProgress: 50%");
    stateful = stateful.appendData("\rProgress: 100%");

    expect(stateful.data).toBe("Progress: 100%");
  });

  test("appendData maintains ANSI state", () => {
    const message = {
      mimetype: "text/plain",
      channel: "stdout",
      timestamp: 0,
      data: "Line 1\n",
    } as const;
    let stateful = StatefulOutputMessage.create(message);

    stateful = stateful.appendData("Line 2\n");
    stateful = stateful.appendData("\u001B[1A"); // Move up
    stateful = stateful.appendData("X");

    expect(stateful.data).toMatchInlineSnapshot(`
      "Line 1
      Xine 2"
    `);
  });
});
