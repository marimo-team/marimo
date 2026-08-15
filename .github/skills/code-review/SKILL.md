---
name: code-review
description: Format every Copilot pull request review line comment and overview with copy-pasteable prompts for AI agents. Use this skill for every pull request code review.
license: Apache-2.0
---

## Review comment format

End every review comment you leave on a line of code with the block below.
Fill each placeholder. Reproduce the wording, the `<details>` element, and the
fence exactly as shown. Do not include the `~~~` lines.

~~~
<details>
<summary>Prompt for AI agents</summary>

`````text
Check if this issue is valid. If so, find the root cause and fix it. At <FILE_PATH>, line <LINE_NUMBER>:

<comment severity="<low|medium|high>"><THE TEXT OF YOUR REVIEW COMMENT></comment>

<file context>
<THE DIFF HUNK YOU COMMENTED ON>
</file context>
`````

</details>
~~~

## Overview comment format

End the pull request overview comment with the block below. List every issue
you raised in the review. Group the issues by file. Number them from 1 within
each file. Use one `<file>` element per file and one `<violation>` element per
issue. Set `severity` to the same value you assigned the issue: `low`,
`medium`, or `high`. Order the issues from `high` to `low` within each file.
Do not include the `~~~` lines.

~~~
<details>
<summary>Prompt for AI agents</summary>

`````text
Check if these issues are valid — if so, understand the root cause of each and fix them. If appropriate, use sub-agents to investigate and fix each issue separately.

<file name="<FILE_PATH>">

<violation number="<N>" severity="<low|medium|high>" location="<FILE_PATH>:<LINE_NUMBER>">
<THE TEXT OF THE REVIEW COMMENT FOR THIS ISSUE>
</violation>

</file>
`````

</details>
~~~
