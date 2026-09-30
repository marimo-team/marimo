# Editor AI benchmark results

This file is the running experiment log for marimo's editor AI harness. Keep
results here as strategies change so prompt and tool experiments remain
comparable over time.

## Method

- Model: `deepseek-ai/DeepSeek-V4.1-Flash` through W&B Inference.
- Each trial uses a fresh temporary notebook workspace and the production
  `/api/ai/chat` path.
- Correctness requires the expected public `analysis_summary` values and a
  successful `marimo check`.
- Durations include generation, live-kernel grading, and server shutdown.
- Tool errors are recoverable tool-result errors observed in the assistant
  stream.
- Each chat turn is one complete Logfire trace. Trials and conversations are
  correlated by run, scenario, variant, repetition, and conversation IDs.

The active benchmark registry contains only `baseline` and `hybrid_balanced`.
Rejected prompt, repair, guided-exploration, and persistent-scratch strategies
were removed from executable code after their experiments. Their results below
remain the historical record for why they were rejected.

## Experiment 1: broad validation-first instructions

Date: 2026-09-29

Run: `20260929T055146Z-4a5ea448`

Compared the production code-mode prompt (`baseline`) with additional rules to
inspect before editing, make the smallest coherent change, validate joins and
totals, validate cell execution, and recover deliberately from tool errors
(`validation_first`). Each variant ran three repetitions of one short, one
medium, and one six-turn long scenario.

| Scenario | Variant | Pass rate | Mean duration | Duration SD | Mean tools | Mean tool errors |
|---|---|---:|---:|---:|---:|---:|
| Athletes, short | Baseline | 3/3 | 47.7s | 7.9s | 11.0 | 1.0 |
| Athletes, short | Validation first | 3/3 | 76.2s | 44.3s | 22.7 | 3.0 |
| Retail, medium | Baseline | 3/3 | 111.4s | 21.9s | 15.3 | 1.3 |
| Retail, medium | Validation first | 3/3 | 99.4s | 33.1s | 13.7 | 0.3 |
| Retail, long | Baseline | 3/3 | 356.4s | 105.1s | 26.3 | 1.3 |
| Retail, long | Validation first | 1/3 | 414.7s | 113.4s | 41.3 | 4.0 |
| **Overall** | **Baseline** | **9/9** | **171.8s** | **146.9s** | **17.6** | **1.2** |
| **Overall** | **Validation first** | **7/9** | **196.8s** | **170.7s** | **25.9** | **2.4** |

Validation-first was 14.5% slower overall, used 47% more tools, doubled tool
errors, and reduced pass rate from 100% to 77.8%. It helped the medium task but
caused substantial short-task tail latency and long-task overwork.

Both long-task failures had the same semantic cause: the model created a cell
named `analysis_summary` but did not assign a public dictionary named
`analysis_summary` in the cell body. A marimo cell name is not a public Python
variable. The broad validation rules did not catch this contract violation.

Logfire verification found 48 complete turn traces, 957 spans, exactly one root
per trace, and zero orphaned spans. [Open the run in
Logfire](https://logfire-us.pydantic.dev/shahmir/marimo-ai/?q=attributes-%3E%3E%27marimo.ai.eval.run_id%27+%3D+%2720260929T055146Z-4a5ea448%27&since=2026-09-29T05%3A50%3A00Z&until=2026-09-29T07%3A30%3A00Z).

Conclusion: do not adopt the broad validation-first rules. Test a narrow
completion contract that targets requested public outputs without requiring
more exploration throughout the conversation.

## Experiment 2: completion-contract check

Date: 2026-09-29

Runs: `20260929T065425Z-155ac5fb` and `20260929T070635Z-55ec1c9d`

Added narrow rules for requested public notebook artifacts. The rules explain
that a marimo cell name does not define a Python variable and require one live
kernel check of `analysis_summary` before finishing. Two long trials were used
as a gate; both passed, so a third was run for comparison with Experiment 1.

| Long retail variant | Pass rate | Mean duration | Duration SD | Mean tools | Mean tool errors |
|---|---:|---:|---:|---:|---:|
| Baseline | 3/3 | 356.4s | 105.1s | 26.3 | 1.3 |
| Validation first | 1/3 | 414.7s | 113.4s | 41.3 | 4.0 |
| Completion contract | 3/3 | 441.6s | 132.4s | 35.3 | 4.0 |

Individual completion-contract trials took 438.3s, 281.1s, and 605.4s and used
36, 33, and 37 tools. The strategy restored correctness to 3/3, but compared
with baseline it was 23.9% slower, used 34% more tools, and tripled tool errors.
The third repetition prevented a misleading conclusion from two favorable
trials and confirmed substantial tail latency.

The additional final check was not the only cost: the slowest trial spent most
of its extra work in turns 1 and 2. Adding global prompt rules can change agent
behavior throughout a conversation even when the instruction is nominally
about completion.

Logfire verification found 18 complete turn traces, 279 spans, exactly one root
per trace, and zero orphaned spans. [Open repetitions 1–2 in
Logfire](https://logfire-us.pydantic.dev/shahmir/marimo-ai/?q=attributes-%3E%3E%27marimo.ai.eval.run_id%27+%3D+%2720260929T065425Z-155ac5fb%27&since=2026-09-29T06%3A50%3A00Z&until=2026-09-29T07%3A10%3A00Z)
and [repetition 3](https://logfire-us.pydantic.dev/shahmir/marimo-ai/?q=attributes-%3E%3E%27marimo.ai.eval.run_id%27+%3D+%2720260929T070635Z-55ec1c9d%27&since=2026-09-29T07%3A05%3A00Z&until=2026-09-29T07%3A30%3A00Z).

Conclusion: the failure mode is addressable, but do not adopt this prompt. Next
test a smaller cell-semantics rule that prevents the underlying cell-name
confusion without requiring an explicit final validation action.

## Experiment 3: cell-semantics rule

Date: 2026-09-29

Run: `20260929T071804Z-da53e23e`

Replaced the explicit completion check with a smaller rule: use anonymous cells
unless a stable name is required, treat cell names only as identifiers, and
assign and return requested public variables in the cell body. The plan was to
gate on two long trials and run a third only if both correctness and efficiency
were promising.

| Trial | Passed | Duration | Tools | Tool errors | Result |
|---|---:|---:|---:|---:|---|
| 1 | Yes | 584.1s | 51 | 2 | Correct summary, severe initial-turn overwork |
| 2 | No | 292.8s | 25 | 1 | Stored percent change as `-0.3859` instead of `-38.6` |
| **Pilot mean** | **1/2** | **438.4s** | **38.0** | **1.5** | **Stopped after gate** |

The rule prevented the cell-name/public-variable failure in these two trials,
but it did not improve the harness overall. One trial was a severe efficiency
outlier, and the other introduced a distinct unit/scale error. A third trial
was not justified.

Logfire verification found 12 complete turn traces, 200 spans, exactly one root
per trace, and zero orphaned spans. [Open the run in
Logfire](https://logfire-us.pydantic.dev/shahmir/marimo-ai/?q=attributes-%3E%3E%27marimo.ai.eval.run_id%27+%3D+%2720260929T071804Z-da53e23e%27&since=2026-09-29T07%3A15%3A00Z&until=2026-09-29T07%3A40%3A00Z).

Conclusion: stop adding global prompt rules for this failure. Baseline remains
the best tested strategy. The next direction should enforce artifact contracts
at the harness or tool boundary, after generation, so it cannot perturb every
turn. A postcondition failure should trigger one focused repair rather than
more general-purpose validation instructions.

## Experiment 4: harness-level postcondition repair

Date: 2026-09-29

Runs: `20260929T073618Z-85a0ef72` and `20260929T075509Z-5dac20f9`

Kept the baseline system prompt unchanged. After the final requested turn, the
runner inspected the live kernel for a public `analysis_summary` dictionary
with the required keys. A valid notebook incurred no extra model call. A
failed postcondition produced one focused repair turn containing the exact
contract error and explicitly forbidding unrelated analysis or presentation
work.

| Trial | Passed | Total duration | Total tools | Repair | Repair cost |
|---|---:|---:|---:|---|---:|
| 1 | Yes | 709.4s | 55 | Succeeded | 20.5s, 3 tools |
| 2 | Yes | 404.6s | 29 | Not needed | None |
| 3 | Yes | 431.4s | 39 | Succeeded | 10.7s, 2 tools |
| **Mean / total** | **3/3** | **515.1s** | **41.0** | **2/2 succeeded** | **15.6s, 2.5 tools** |

The total-duration and tool means should not be compared directly with the
earlier three baseline samples: trial 1's six baseline turns were already a
severe 676-second, 52-tool outlier before repair began. The experimental
increment is observable separately. Across the two failed contracts, repair
added an average 15.6 seconds and 2.5 tools with zero repair-turn tool errors.
The already-valid trial incurred no seventh turn.

This is the first strategy that improved correctness without changing earlier
conversation behavior. It retained a 3/3 pass rate, detected two real
structural failures, and repaired both with bounded incremental cost.

Logfire verification found 20 complete turn traces, including two repair
traces, 316 spans, exactly one root per trace, and zero orphaned spans. [Open
repetitions 1–2 in
Logfire](https://logfire-us.pydantic.dev/shahmir/marimo-ai/?q=attributes-%3E%3E%27marimo.ai.eval.run_id%27+%3D+%2720260929T073618Z-85a0ef72%27&since=2026-09-29T07%3A35%3A00Z&until=2026-09-29T08%3A00%3A00Z)
and [repetition 3](https://logfire-us.pydantic.dev/shahmir/marimo-ai/?q=attributes-%3E%3E%27marimo.ai.eval.run_id%27+%3D+%2720260929T075509Z-5dac20f9%27&since=2026-09-29T07%3A55%3A00Z&until=2026-09-29T08%3A10%3A00Z).

Conclusion: continue with postcondition repair. The next engineering step is to
represent artifact contracts explicitly rather than deriving this benchmark's
contract from expected-summary keys. That contract can then support public
variables, expected types and keys, notebook execution errors, and other editor
surfaces without putting validation instructions in every model turn.

## Experiment 5: hybrid exploration and typed notebook tools

Date: 2026-09-29

Run: `20260929T082215Z-352db35b`

The benchmark-specific postcondition repair from Experiment 4 is not a
general production strategy. This experiment instead changed the model's
notebook interface. It retained `execute_code` for exploratory Python and
added typed tools for inspection, insertion, editing, deletion, and execution.
The typed mutation tools compile to the existing `_code_mode` transaction API,
so notebook validation and persistence still have one implementation.

The first smoke run exposed a zero-argument tool interoperability issue: the
model added invented arguments to `inspect_notebook`. Requiring the literal
argument `scope="all"` fixed it. A second smoke run showed that embedding the
old `marimo-pair` skill was contradictory: it still required `help(cm)` and
instructed the model to mutate through `execute_code`. The final variant uses
a dedicated, shorter hybrid skill and rejects `_code_mode` imports in the
exploration tool.

One repetition of three deliberately different cases was used as a screen:

| Scenario | Variant | Passed | Duration | Tools | Tool errors |
|---|---|---:|---:|---:|---:|
| Ticket targeted repair, short | Baseline | Yes | 65.1s | 12 | 0 |
| Ticket targeted repair, short | Hybrid | Yes | 83.5s | 23 | 4 |
| Reactive dependency repair, medium | Baseline | Yes | 61.3s | 13 | 1 |
| Reactive dependency repair, medium | Hybrid | Yes | 32.3s | 13 | 0 |
| Retail investigation, six turns | Baseline | No | 198.9s | 22 | 1 |
| Retail investigation, six turns | Hybrid | Yes | 231.7s | 60 | 0 |
| **Overall** | **Baseline** | **2/3** | **108.4s mean** | **15.7 mean** | **0.7 mean** |
| **Overall** | **Hybrid** | **3/3** | **115.8s mean** | **32.0 mean** | **1.3 mean** |

The hybrid variant preserved the final public artifact in the long
conversation. The baseline completed all six turns but never created a live
`analysis_summary`; the hybrid produced the expected five values. This is a
promising reliability signal because it emerged from a general tool boundary,
not knowledge of benchmark keys.

The cost is currently too high. Hybrid used 60 tools in the long case versus
22 for baseline, and its targeted-repair trajectory overworked a small change.
The four targeted-repair errors were recoverable but revealing: one duplicate
import, one dependent cell run before stale ancestors, one syntax error, and a
follow-on read of the value that the failed edit would have defined. Typed
tools made these failures more legible; they did not prevent poor planning.

Logfire verification found 16 complete turn traces, 329 spans, exactly one
root per trace, and zero orphaned spans.

Conclusion: the hybrid boundary is worth iterating on, but do not promote this
version or spend on a full repeated matrix. The next variant should reduce the
surface and round trips: return graph ownership and dependency state from
inspection, support an atomic multi-cell patch, and have the server execute
the affected dependency closure once. Then repeat this three-case screen. Only
run repetitions if correctness holds and tool count approaches baseline.

## Experiment 6: atomic dependency-aware notebook patch

Date: 2026-09-29

Runs: `20260929T083937Z-24c8b74f` and `20260929T085202Z-12a4f455`

Replaced the three granular mutation tools with one `apply_notebook_patch`
tool. It accepts multiple cell replacements, inserts, and deletes, validates
all structural changes in one `_code_mode` transaction, then runs initially
stale and patched cells as one dependency-ordered batch. Inspection now
returns static definitions, references, parents, and children even before the
initial notebook execution.

The one-repetition screen passed for both variants and justified two fresh
repetitions. Combined results are:

| Scenario | Variant | Pass rate | Mean duration | Duration SD | Mean tools | Mean tool errors |
|---|---|---:|---:|---:|---:|---:|
| Ticket repair, short | Baseline | 3/3 | 40.5s | 13.1s | 9.7 | 1.0 |
| Ticket repair, short | Atomic hybrid | 3/3 | 24.5s | 5.7s | 8.7 | 0.7 |
| Reactive repair, medium | Baseline | 3/3 | 40.5s | 3.1s | 10.0 | 2.3 |
| Reactive repair, medium | Atomic hybrid | 3/3 | 38.6s | 21.6s | 11.0 | 2.0 |
| Retail, six turns | Baseline | 2/3 | 374.2s | 59.2s | 39.0 | 3.7 |
| Retail, six turns | Atomic hybrid | 2/3 | 216.1s | 70.8s | 33.7 | 2.3 |
| **Overall** | **Baseline** | **8/9** | **151.8s** | — | **19.6** | **2.3** |
| **Overall** | **Atomic hybrid** | **8/9** | **93.1s** | — | **17.8** | **1.7** |

Atomic hybrid matched correctness while reducing mean duration by 38.7%, tool
calls by 9.1%, and tool errors by 28.6%. The improvement was largest in long
conversations: later requirement changes usually became one coherent patch
plus a small validation sequence instead of many granular mutations.

One reactive hybrid trial remained a planning outlier at 68.9 seconds, 20
tools, and five errors. Atomic application reduces round trips on a good plan;
it does not guarantee a good plan.

Both long failures had the same cause. The model created a cell named
`analysis_summary` but its body defined five individual values instead of a
public dictionary. In the hybrid failure it then inspected the dependency
metadata, saw that `analysis_summary` was absent from `defines`, and still
validated only the individual values. A cell name remains an attractive but
false proxy for a Python definition.

Logfire verification found 48 complete turn traces, 844 spans, exactly one
root per trace, and zero orphaned spans.

Conclusion: atomic patching is a meaningful general improvement, but cell
naming should not be exposed on the simple insertion surface. New cells can be
anonymous and addressed by the stable IDs returned by the server. This removes
the false name/variable affordance without embedding knowledge of benchmark
artifacts. Gate that change on repeated long conversations.

## Experiment 7: anonymous atomic inserts

Date: 2026-09-29

Runs: `20260929T091810Z-ab3dcb92` and `20260929T092517Z-7d0cce40`

Removed the optional cell `name` from new-cell patches. Inserts are anonymous
and the server-returned cell ID is their handle. Existing named cells retain
their names when edited. This keeps cell metadata out of the simple authoring
surface and forces requested public artifacts to be assigned in code.

Three six-turn retail trials produced:

| Trial | Artifact existed | Score passed | Duration | Tools | Tool errors |
|---|---:|---:|---:|---:|---:|
| 1 | Yes | Yes | 205.3s | 25 | 0 |
| 2 | Yes | Yes | 212.3s | 29 | 1 |
| 3 | Yes | No | 226.6s | 38 | 6 |
| **Mean / rate** | **3/3** | **2/3** | **214.7s** | **30.7** | **2.3** |

The structural failure was eliminated in all three trials: every final
notebook defined a live public `analysis_summary` dictionary. The third trial
failed only the numeric grader because it stored `percent_change` as the ratio
`-0.3859` while the expected value was percentage points `-38.6`. The scenario
asked for `percent_change` without specifying units, so both representations
were reasonable. This is an evaluation-contract ambiguity, not a missing
artifact or notebook failure.

Logfire verification found 18 complete turn traces, 257 spans, exactly one
root per trace, and zero orphaned spans.

Conclusion: keep anonymous inserts. Clarify the retail benchmark to require
percentage points, then use a paired long run to verify the revised task. Do
not add a production prompt rule or output-specific repair for an ambiguity in
the evaluator.

## Experiment 8: clarified percentage contract

Date: 2026-09-29

Run: `20260929T093007Z-96d0cfaa`

Clarified that `percent_change` is expressed in percentage points (`12.5` for
12.5%, not `0.125`) in both retail scenarios. This removes an evaluator
ambiguity without changing the production harness. One paired six-turn trial
verified the revised contract.

| Variant | Passed | Duration | Tools | Tool errors |
|---|---:|---:|---:|---:|
| Baseline | Yes | 383.2s | 42 | 1 |
| Anonymous atomic hybrid | Yes | 557.3s | 61 | 5 |

Both produced the expected five-value dictionary with percentage points. The
hybrid trial was a severe latency and tool-count outlier. Logfire attribution
showed 41 `execute_code` calls, nine successful atomic patches, eight notebook
inspections, and three capability loads. The structural tool was not the
bottleneck: every patch succeeded. Unbounded exploratory scratchpad use caused
the overwork and all five failed tool results.

Logfire verification found 12 complete turn traces, 253 spans, exactly one
root per trace, and zero orphaned spans.

Conclusion: the anonymous atomic patch is the best structural interface tested
and should remain the candidate, but it is not sufficient by itself. The next
general harness experiment should constrain or consolidate exploration rather
than add more mutation tools. Candidate mechanisms are a per-turn exploratory
call budget with a graceful synthesis phase, persistent scratch state, or one
typed data-inspection tool that batches schema, sample, and validation output.

## Experiment 9: soft exploration checkpoint

Date: 2026-09-29

Run: `20260929T095313Z-2b48a717`

Added a `hybrid_guided` benchmark strategy with the same anonymous atomic
hybrid tools. On the fifth and each subsequent `execute_code` call within one
chat turn, the successful tool result included a non-blocking checkpoint. It
asked the model to synthesize existing evidence, prefer one coherent patch and
one focused validation, and continue exploring only for a specific unresolved
question. The tool still executed normally, so the policy could not prevent a
hard task from completing.

One paired short/medium/long screen produced:

| Scenario | Variant | Passed | Duration | Tools | Tool errors |
|---|---|---:|---:|---:|---:|
| Ticket repair, short | Atomic hybrid | Yes | 31.5s | 10 | 0 |
| Ticket repair, short | Guided hybrid | Yes | 31.5s | 8 | 1 |
| Reactive repair, medium | Atomic hybrid | Yes | 34.4s | 12 | 3 |
| Reactive repair, medium | Guided hybrid | Yes | 20.4s | 7 | 1 |
| Retail, six turns | Atomic hybrid | Yes | 272.4s | 33 | 0 |
| Retail, six turns | Guided hybrid | Yes | 317.6s | 43 | 3 |
| **Overall mean** | **Atomic hybrid** | **3/3** | **112.8s** | **18.3** | **1.0** |
| **Overall mean** | **Guided hybrid** | **3/3** | **123.2s** | **19.3** | **1.7** |

The short and medium guided trials made only two exploratory calls each, so
the checkpoint never activated. Their lower tool counts are ordinary model
variance and cannot be attributed to the policy. Only the first two guided
long turns activated it, with seven and eight `execute_code` calls. The model
continued exploring after every checkpoint instead of transitioning cleanly
to synthesis.

Across all three trials, Logfire recorded 26 guided `execute_code` calls versus
23 unguided calls. Guided also used 12 patches, 10 inspections, six explicit
cell runs, and four capability loads; unguided used nine patches, 13
inspections, five cell runs, and five capability loads. The cue shifted the
trajectory but did not reduce total work. In the long task it increased
duration by 16.6% and tool calls by 30.3%.

Trace verification found 278 spans across 16 turn traces, exactly one root per
trace, and zero orphaned spans.

Conclusion: stop this strategy after the screen. Repeating it would measure
variance around a mechanism that failed its causal test. A text cue embedded
in repeated scratchpad results is too weak and can itself add context and
replanning. The next exploration experiment should improve information
density per call, such as a typed data-profile tool that returns schema,
missingness, compact samples, and safe summaries together. That attacks the
reason for repeated exploration rather than asking the model to stop.

## Experiment 10: turn-scoped persistent scratch state

Date: 2026-09-29

Runs: `20260929T102426Z-00adc670` and
`20260929T103518Z-0f695343`

Added a kernel-owned scratch namespace that persists top-level bindings across
`execute_code` calls within one assistant turn. Every call starts with fresh
live notebook globals overlaid by the turn's scratch bindings. The namespace
is isolated from the notebook dependency graph and is released from the
streaming response's `finally` path, including cancellation and early stream
closure. A new turn receives a new namespace.

The initial paired screen produced:

| Scenario | Variant | Passed | Duration | Tools | Tool errors |
|---|---|---:|---:|---:|---:|
| Reactive repair | Atomic hybrid | Yes | 25.2s | 7 | 1 |
| Reactive repair | Persistent hybrid | Yes | 24.5s | 9 | 1 |
| Retail, six turns | Atomic hybrid | Yes | 231.0s | 33 | 0 |
| Retail, six turns | Persistent hybrid | Yes | 287.3s | 33 | 2 |

Persistence was neutral on the reactive task and 24.4% slower on the long
task. Logfire showed why the mechanism did not help: in the first long turn,
the model assigned `orders`, `customers`, and `returns`, then loaded all three
files again in its next exploration call. The state existed, but the model did
not trust or remember that it existed from the tool description alone.

A focused refinement reported up to 20 persistent names and their types after
every call and added an explicit system instruction to reuse them. The model
then successfully reused `_customers`, `_orders`, and `_returns` in the next
call, proving that the runtime behavior and feedback worked. That reused call
failed due to an unrelated Polars expression, after which the model reloaded
the data under new names.

The refined six-turn trial still passed, but regressed further:

| Variant | Passed | Duration | Tools | Tool errors |
|---|---:|---:|---:|---:|
| Atomic hybrid control from paired run | Yes | 231.0s | 33 | 0 |
| Persistent state, description only | Yes | 287.3s | 33 | 2 |
| Persistent state with inventory | Yes | 405.0s | 56 | 8 |

The refined run contained 32 `execute_code` calls, nine inspections, eight
patches, four explicit cell runs, and three capability loads. Compared with
the paired atomic control, it was 75.4% slower and used 69.7% more tools. The
inventory increased awareness of scratch state but also added context after
every call and encouraged more interaction. Most later-turn exploration read
durable notebook variables created by earlier patches, where temporary state
provided no advantage.

Across both runs, Logfire contained 347 spans in 20 turn traces, exactly one
root per trace, and zero orphaned spans.

Conclusion: stop this strategy after the scoped screen. Turn-local state is a
sound REPL primitive and may help computationally expensive workflows, but
these representative notebook tasks did not benefit. Automatic state
inventories made the harness materially worse. Do not replace persistence
with transparent result caching: live notebook state, mutable objects, I/O,
randomness, and side effects make cache validity unsafe. The next experiment
should improve the structure and density of observations while leaving
`execute_code` stateless and unrestricted.

## Experiment 11: breadth screen and outlier confirmation

Date: 2026-09-29

Runs: `20260929T105204Z-84b0809c` and
`20260929T111535Z-2d52dbbb`

Compared the baseline and anonymous atomic hybrid on the seven scenarios not
included in the earlier repeated three-case matrix. This was a one-repetition
breadth screen, followed by two-repetition confirmation on the fastest hybrid
win and the single hybrid failure.

| Breadth-screen aggregate | Passed | Mean duration | Mean tools | Mean tool errors |
|---|---:|---:|---:|---:|
| Baseline | 7/7 | 88.6s | 17.0 | 1.29 |
| Atomic hybrid | 6/7 | 104.1s | 21.3 | 0.86 |

The hybrid was faster on `athletes_prescribed`,
`inventory_schema_inspection`, and `saas_requirement_reversal`; approximately
neutral on `retail_investigation_short`; and slower on
`subscriptions_dirty_dates` and `orders_missing_dimensions`. Its only failure
was `operations_context_pressure`: 367.2 seconds, 57 tools, and five tool
errors, versus a passing baseline at 218.9 seconds, 41 tools, and one error.
The final value was semantically correct but stored as a one-row Polars frame
instead of the required dictionary.

The failed long trial's second turn accounted for 114.9 seconds, 24 tools, and
all five errors. Its first patch defined `_labels` but referenced `labels`.
After the resulting `NameError`, the model spent most of the turn inspecting
marimo's AST visitor, compiler, cell definitions and references, runtime graph,
and session analysis before noticing the local identifier mismatch. This was
failed-edit recovery thrash, not useful data exploration.

The confirmation run used `--jobs 2`, validating bounded parallel execution.
All eight trials passed:

| Scenario | Variant | Passed | Mean duration | Mean tools | Mean tool errors |
|---|---|---:|---:|---:|---:|
| Inventory inspection | Baseline | 2/2 | 52.9s | 11.5 | 1.0 |
| Inventory inspection | Atomic hybrid | 2/2 | 38.7s | 11.5 | 0.0 |
| Operations context | Baseline | 2/2 | 402.2s | 53.0 | 4.5 |
| Operations context | Atomic hybrid | 2/2 | 179.2s | 37.5 | 2.0 |

The second baseline long trial independently produced a recovery spiral: it
took 602.0 seconds, 77 tools, and eight errors; one turn alone took 192.3
seconds, 25 tools, and five errors. Both confirmed hybrid long trials passed in
175.7--182.6 seconds. One used 42 tools and three errors, while the other used
33 tools and one error. Neither repeated the compiler/runtime investigation.

Conclusion: the original 57-tool hybrid failure is not representative evidence
that typed tools inherently cause excessive exploration. Long tasks have high
trajectory variance, and both variants can over-investigate after a local
failure. The hybrid exposes more possible investigative paths and can amplify
that behavior, but it remained substantially faster and more reliable in this
small confirmation. The next focused strategy should improve failure-recovery
escalation: after a mutation error, compare the exact failing source with the
error and attempt the smallest local correction before inspecting framework
internals. This is preferable to limiting legitimate exploratory analysis.

## Experiment 12: preserve child-cell diagnostics

Date: 2026-09-29

Run: `20260929T132146Z-c94be538`

The failed patch in Experiment 11 revealed that the model did not receive the
diagnostic originally attributed to it. The actual `apply_notebook_patch`
result contained only `cell 'dWkU' raised NameError`; its `stderr` was empty.
A subsequent notebook inspection exposed `name 'labels' is not defined` and
the complete source, but still no traceback location.

The runtime already emits child-cell tracebacks containing the stable cell ID,
line number, failing source line, and caret. The blocking scratchpad path
observed these console notifications but discarded them while waiting. It also
discarded each structured error's `msg`, retaining only `exception_type`.

Changed the shared scratchpad result boundary to:

- preserve child error type and message in `errors`, without duplicating an
  exception-type prefix already present in the message;
- collect child-cell stderr, including the plain-text traceback emitted during
  code-mode execution; and
- append that stderr to `CodeExecutionResult.stderr` while leaving the SSE
  streaming path unchanged.

Focused server and AI-tool tests passed: 52 tests, plus Ruff, format, and diff
checks. The end-to-end scratchpad test now verifies a result containing
`cell 'child-cell' raised ZeroDivisionError: division by zero` and a traceback
with `<cell-child-cell>`, line 1, the failing expression, and the exception.

Two parallel `operations_context_pressure` hybrid trials then produced:

| Trial | Passed | Duration | Tools | Tool errors |
|---|---:|---:|---:|---:|
| 1 | Yes | 395.3s | 47 | 2 |
| 2 | Yes | 218.2s | 33 | 2 |
| **Mean** | **2/2** | **306.7s** | **40.0** | **2.0** |

No turn reproduced the earlier 24-call mutation-recovery spiral. Error-bearing
turns used five to seven tools. However, Logfire inspection showed that all
four errors in these trials came directly from exploratory scratch code, whose
own tracebacks were already returned; no typed patch or explicit cell-run call
failed. The behavioral run is therefore a useful non-regression result but not
a causal measurement of the new child-cell diagnostics. The deterministic
end-to-end test is the direct verification of the repaired information path.

Conclusion: keep this change. It fixes a real loss of runtime information at a
shared boundary and benefits baseline code mode as well as hybrid tools. A
future mutation-recovery benchmark can deliberately exercise a failing child
cell if we want a stable behavioral measurement, but it is not necessary to
justify preserving diagnostics that the runtime already produced.

After pruning the rejected executable variants, run
`20260929T134526Z-343d93d0` verified the remaining hybrid path end to end on
`inventory_schema_inspection`: pass, 32.5 seconds, seven tools, and zero tool
errors.

## Experiment 13: targeted paired confirmation

Date: 2026-09-29

Run: `20260929T134914Z-8431f223`

Ran two fresh repetitions of baseline and anonymous atomic hybrid on five
previously ambiguous scenarios. The 20 isolated trials ran with four workers.
Every trial passed its public-summary contract and `marimo check`.

| Scenario | Variant | Passed | Mean duration | Mean tools | Mean tool errors |
|---|---|---:|---:|---:|---:|
| Retail investigation | Baseline | 2/2 | 168.9s | 19.5 | 3.0 |
| Retail investigation | Atomic hybrid | 2/2 | 99.8s | 13.5 | 0.5 |
| Dirty subscription dates | Baseline | 2/2 | 67.2s | 9.0 | 1.5 |
| Dirty subscription dates | Atomic hybrid | 2/2 | 45.4s | 9.5 | 0.5 |
| Missing order dimensions | Baseline | 2/2 | 67.2s | 11.0 | 1.0 |
| Missing order dimensions | Atomic hybrid | 2/2 | 42.3s | 11.0 | 0.0 |
| SaaS requirement reversal | Baseline | 2/2 | 310.7s | 32.5 | 1.5 |
| SaaS requirement reversal | Atomic hybrid | 2/2 | 247.6s | 27.0 | 1.0 |
| Operations context pressure | Baseline | 2/2 | 282.3s | 29.0 | 1.0 |
| Operations context pressure | Atomic hybrid | 2/2 | 221.5s | 31.5 | 0.5 |
| **Overall** | **Baseline** | **10/10** | **179.3s** | **20.2** | **1.6** |
| **Overall** | **Atomic hybrid** | **10/10** | **131.3s** | **18.5** | **0.5** |

The hybrid reduced mean duration by 26.7%, tool calls by 8.4%, and tool errors
by 68.8% with equal correctness. Every scenario's hybrid duration mean was
lower. For the six medium trials, hybrid was 38.2% faster; for the four long
trials, it was 20.9% faster. The duration standard deviation was also lower
overall (91.3 seconds versus 125.5 seconds), although both variants retained
large generation-latency tails.

Atomic tools did not reduce calls universally. Hybrid used slightly more calls
on dirty dates and operations context, tied on missing dimensions, and used
fewer on retail and SaaS. The stronger result is that its calls were more
reliable: only five tool errors across ten trials, versus sixteen for baseline.

Logfire contained 1,006 spans across 64 complete turn traces. Every trace had
exactly one root span.

Conclusion: this resolves the earlier ambiguous breadth result in favor of the
anonymous atomic hybrid for this model and code-mode suite. Adding more similar
code-mode cases is now lower value than testing model portability and the two
other editor surfaces. Keep the current ten code-mode scenarios as the local
regression suite; next evaluate the hybrid with another strong model, then
build separate contracts for inline completion and Generate with AI.

### Token-usage backfill

The original local artifacts reported zero tokens because the Vercel stream's
finish event does not include Pydantic AI run usage. Logfire retained exact
usage on each model-request span, so the 20 trials were backfilled by joining
each eval turn root to its child model spans and summing usage by trial.

| Variant | Trials | Model requests | Mean input tokens | Mean output tokens | Mean reasoning tokens | Mean cache-read tokens |
|---|---:|---:|---:|---:|---:|---:|
| Baseline | 10 | 231 | 717,002 | 28,826 | 19,219 | 486,541 |
| Atomic hybrid | 10 | 196 | 490,374 | 19,968 | 12,196 | 280,294 |

Across equally successful trials, hybrid used 15.2% fewer model requests,
31.6% fewer input tokens, 30.7% fewer output tokens, and 36.5% fewer reasoning
tokens. Cache-read tokens were 42.4% lower. Since cached tokens are included in
input tokens, the uncached-input reduction was smaller: 8.8%. This distinction
matters for latency and cost analysis and should remain visible rather than
collapsing usage into one total.

The aggregate win was not universal:

| Scenario | Baseline mean input | Hybrid mean input | Change | Baseline mean output | Hybrid mean output |
|---|---:|---:|---:|---:|---:|
| Retail investigation | 1,051,770 | 182,213 | -82.7% | 32,303 | 18,711 |
| Dirty subscription dates | 102,286 | 55,259 | -46.0% | 12,588 | 8,305 |
| Missing order dimensions | 128,567 | 335,432 | +160.9% | 10,063 | 6,868 |
| SaaS requirement reversal | 1,418,316 | 872,933 | -38.4% | 53,384 | 35,691 |
| Operations context pressure | 884,070 | 1,006,034 | +13.8% | 35,791 | 30,265 |

The missing-dimensions regression came from one 575,297-input-token hybrid
outlier; its paired hybrid repetition used 95,567. Token counts therefore add
important trajectory-cost evidence but retain the same variance problem as
latency. The hybrid conclusion remains favorable overall, with an explicit
follow-up to investigate high-input outliers on individual scenarios.

Future artifacts now request completed-run usage directly from Pydantic AI and
store it at turn, trial, scenario, length, and variant levels. A live baseline
trial (`20260929T141246Z-7088ee55`) recorded 13 model requests, 124,825 input
tokens, 7,337 output tokens, 3,902 reasoning tokens, and 82,944 cache-read
tokens. Logfire returned the exact same totals for its trace, validating the
new collection path end to end.

## Experiment 14: editor capability coverage and balanced tools

Date: 2026-09-29

Runs: `20260929T150010Z-0218f3d7`, `20260929T150112Z-a810917d`,
`20260929T150812Z-edd167e2`, `20260929T150814Z-afcd3c71`

Added three deterministic capability cases that complement the ten data and
conversation cases:

- `package_lifecycle` installs a local wheel, then replaces and removes it in
  a second turn. Its server runs in a disposable child virtual environment.
- `ui_state_interaction` changes a live slider value and checks reactive output
  while requiring the saved source to retain its original default.
- `cell_layout_configuration` changes `hide_code`, `expand_output`, and visual
  order while requiring the computation and source bodies to remain intact.

The grader now supports required source fragments, forbidden fragments, and
source ordering in addition to live `analysis_summary` values and
`marimo check`. This prevents a numerically correct result from passing after
the model took the wrong kind of editor action.

The new `hybrid_balanced` strategy retains the four atomic hybrid tools and
adds three grouped operations: `manage_packages`, `set_ui_value`, and
`configure_notebook`. Each compiles to the existing `_code_mode` transaction
layer. The production baseline remains the single expressive `execute_code`
tool, while `hybrid_tools` remains the narrower four-tool strategy.

An initial balanced-only screen passed all three cases:

| Scenario | Passed | Duration | Tools | Errors | Input tokens |
|---|---:|---:|---:|---:|---:|
| Package lifecycle | Yes | 44.8s | 14 | 1 | 88,135 |
| UI state | Yes | 10.7s | 4 | 0 | 14,283 |
| Cell layout | Yes | 12.0s | 5 | 0 | 18,411 |

The first three-way comparison produced the following aggregate. The narrow
hybrid layout trial reached Pydantic AI's 50-request limit; because the stream
did not complete, its partial calls and tokens are absent from the artifact,
so its aggregate understates its actual cost.

| Variant | Passed | Mean duration | Mean tools | Mean errors | Mean input tokens |
|---|---:|---:|---:|---:|---:|
| Baseline | 3/3 | 51.6s | 12.7 | 2.0 | 144,505 |
| Narrow atomic hybrid | 2/3 | 182.8s | 22.7 | 1.3 | 768,603 |
| Balanced hybrid | 2/3 | 28.0s | 9.7 | 0.3 | 321,088 |

The balanced failure was not a failed package operation. The model installed
and removed the correct wheels, updated the notebook, and returned the correct
values, but interpreted “set `analysis_summary` to” as permission to create a
formatted string. The grader correctly rejected it because the inspection
contract requires a dictionary. The scenario now explicitly names the
dictionary keys. Two fresh balanced repetitions then both passed with zero
tool errors:

| Passed | Mean duration | Mean tools | Mean input | Mean output | Mean reasoning |
|---:|---:|---:|---:|---:|---:|
| 2/2 | 36.9s | 13.0 | 71,842 | 3,277 | 1,494 |

The narrow hybrid could technically perform package and UI operations by
searching internal implementation APIs from exploratory Python. That is not a
good substitute for capability coverage. Its package trial used 45 tools,
1,965,825 input tokens, and 240.9 seconds. Its UI trial used 23 tools and
339,984 input tokens. Its layout trial never completed. In contrast, the
balanced tools expressed the intent directly and retained the shared
transaction implementation.

To check for tool bloat, ran the narrow and balanced hybrids on the two normal
data-analysis cases in the quick suite. All four trials passed:

| Variant | Passed | Mean duration | Mean tools | Mean errors | Mean input | Mean output |
|---|---:|---:|---:|---:|---:|---:|
| Narrow atomic hybrid | 2/2 | 94.7s | 13.0 | 1.5 | 176,820 | 14,895 |
| Balanced hybrid | 2/2 | 49.4s | 8.5 | 0.0 | 51,818 | 5,539 |

In this small paired sample, the extra three tools did not distract the model:
the balanced strategy was 47.9% faster and used 70.7% fewer input tokens. This
is not enough evidence to claim those exact improvements generally—the narrow
retail trial was an expensive trajectory outlier—but it rejects the immediate
hypothesis that seven well-grouped tools necessarily produce tool bloat.

Conclusion: keep the capability cases and disposable package environment.
Keep the balanced variant as the leading experimental architecture. The main
lesson is not “more tools are always better”; it is that high-value editor
operations need first-class, intent-level affordances. Missing capabilities
encourage fragile internal-API exploration that is slower, more expensive,
and harder to support. Before considering this production-ready, repeat the
balanced strategy on the full data suite and another strong model, and add a
separate screenshot-backed visual-correction case once benchmark tool outputs
can carry images reliably.

## Experiment 15: focused baseline versus balanced confirmation

Date: 2026-09-29

Run: `20260929T154627Z-9b52bb9c`

Compared the production baseline and seven-tool balanced hybrid on three
representative data tasks with two fresh repetitions each: multi-table retail
analysis, reactive dependency repair, and the seven-turn operations context
case. All twelve trials passed their summary contracts and `marimo check`.

| Variant | Passed | Mean duration | Mean tools | Mean errors | Mean requests | Mean input | Mean output | Mean reasoning |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Baseline | 6/6 | 147.0s | 22.3 | 1.67 | 23.8 | 649,412 | 23,088 | 14,856 |
| Balanced hybrid | 6/6 | 132.4s | 18.0 | 1.33 | 19.3 | 498,549 | 20,636 | 13,449 |

With equal correctness, the balanced hybrid was 10.0% faster, used 19.4%
fewer tools, 18.9% fewer model requests, 23.2% fewer input tokens, 10.6% fewer
output tokens, and 20.0% fewer tool errors. Removing cache-read tokens from
input tokens yields 213,700 mean uncached input tokens for baseline and
148,341 for balanced, a 30.6% reduction.

| Scenario | Variant | Passed | Mean duration | Mean tools | Mean errors | Mean input |
|---|---|---:|---:|---:|---:|---:|
| Retail investigation | Baseline | 2/2 | 99.2s | 17.0 | 1.0 | 265,889 |
| Retail investigation | Balanced | 2/2 | 94.4s | 12.0 | 1.0 | 154,473 |
| Reactive repair | Baseline | 2/2 | 58.1s | 11.5 | 2.0 | 134,180 |
| Reactive repair | Balanced | 2/2 | 40.8s | 7.5 | 1.0 | 50,580 |
| Operations context | Baseline | 2/2 | 283.7s | 38.5 | 2.0 | 1,548,169 |
| Operations context | Balanced | 2/2 | 261.9s | 34.5 | 2.0 | 1,290,596 |

The strongest result was reactive repair: balanced was 29.9% faster and used
62.3% fewer input tokens. Retail latency was close and retained trajectory
variance, but balanced used 41.9% fewer input tokens. On the long case,
balanced was 7.7% faster and used 16.6% fewer input tokens. The long result is
important because the added tools did not worsen context retention or compound
cost across seven turns.

Logfire showed that balanced calls remained well targeted across the six
trials: 50 `execute_code`, 23 `inspect_notebook`, 21
`apply_notebook_patch`, seven capability loads, four
`configure_notebook`, and three `run_cells` calls. It never selected
`manage_packages` or `set_ui_value` when those operations were irrelevant.
The four configuration calls occurred on retail, reactive repair, and two
late operations turns, where presentation configuration was a legitimate
notebook concern rather than tool confusion. All 18 balanced turn traces had
exactly one root span in Logfire.

Conclusion: this controlled comparison strengthens the balanced hybrid result.
It matched baseline correctness while reducing work on all three scenarios,
including the long conversation. The evidence now supports a full-suite
confirmation rather than further prompt or tool changes. A second-model run
should follow before treating the architecture as generally superior, since
all behavioral evidence so far uses DeepSeek V4.1 Flash.

## Experiment 16: focused second-model confirmation

Date: 2026-09-30

Model: `Qwen/Qwen3.5-35B-A3B`

Scored runs: `20260929T155820Z-58c5484a`,
`20260929T160950Z-981b7f7b`, and `20260929T161517Z-407f1549`

Ran a staged second-model comparison instead of immediately paying for the
full suite. The four-case screen covers schema inspection, multi-table data
analysis, reactive notebook repair, and a seven-turn context-retention task.
It uses the inventory and reactive trials from the first run, the corrected
retail trials from the second run, and the corrected operations trials from
the final run.

Two benchmark-contract problems surfaced before the scored comparison. The
retail and operations prompts named logical datasets but did not state the
fixture paths. Qwen responded to the empty notebook by creating plausible
synthetic data, so those trials measured prompt inference rather than harness
quality. The prompts now name their CSV inputs. The operations grader also
expected integer exclusion counts while the prompt allowed ID lists. The
final turn now requires a dictionary and explicitly defines both fields as
integer counts. The superseded trials remain useful diagnostics but are not
included below. An attempted smoke run with
`Qwen/Qwen3-Coder-480B-A35B-Instruct` also returned a provider 404 before the
current W&B model ID was selected.

| Variant | Passed | Mean duration | Mean tools | Mean errors | Mean requests | Mean input | Mean output |
|---|---:|---:|---:|---:|---:|---:|---:|
| Baseline | 3/4 | 81.1s | 18.0 | 5.75 | 20.25 | 353,525 | 14,594 |
| Balanced hybrid | 4/4 | 69.6s | 15.75 | 3.75 | 18.5 | 274,741 | 11,025 |

Balanced was 14.2% faster, used 12.5% fewer tools, 34.8% fewer tool errors,
8.6% fewer model requests, 22.3% fewer input tokens, and 24.5% fewer output
tokens. Total input tokens were 1,098,964 for balanced versus 1,414,099 for
baseline. Qwen reported no separate reasoning-token usage. Balanced also used
23.7% fewer cache-read tokens.

| Scenario | Baseline | Balanced | Baseline input | Balanced input |
|---|---:|---:|---:|---:|
| Inventory schema inspection | Pass | Pass | 207,374 | 111,671 |
| Retail investigation | Pass | Pass | 445,983 | 281,189 |
| Reactive dependency repair | Pass | Pass | 208,323 | 52,226 |
| Operations context | Fail | Pass | 552,419 | 653,878 |

The long operations result shows why the benchmark inspects durable notebook
state instead of trusting the assistant's prose. Baseline calculated the
right values in exploratory execution and said it had created
`analysis_summary`, but its saved notebook was still the original empty
eight-line file and the value was absent from the live kernel. Balanced used
more calls and input tokens on this individual case, but committed a valid
331-line notebook and passed all five summary checks plus `marimo check`.

This model has substantially more tool errors than DeepSeek in Experiment 15,
so model-tool compatibility and recovery remain important. Even so, the
direction of the architecture result transferred: balanced improved aggregate
efficiency and was the only variant to pass every focused case. One trial per
case is not enough to estimate exact effect sizes or variance. It is enough to
justify keeping balanced as the leading architecture without running the full
second-model suite yet. The next high-value step is either repeated Qwen runs
on the retail and operations cases or a full DeepSeek suite; repeating the two
high-variance data cases is the cheaper choice if confidence across models is
the immediate goal.

The final parallel operations run produced 14 turn traces. A direct Logfire
query found exactly one root span per trace and 6–18 connected spans per
trace, confirming that concurrent benchmark trials retained navigable trace
trees.

After this confirmation, the four-tool `hybrid_tools` strategy was removed
from the executable benchmark and runtime configuration. Its four atomic
tools remain the foundation of `hybrid_balanced`, which now always includes
the three grouped editor operations. Historical four-tool results above are
retained as the ablation record.

## Experiment 17: full-suite breadth confirmation

Date: 2026-09-30

Model: `deepseek-ai/DeepSeek-V4.1-Flash`

Runs: `20260929T191122Z-994a5b9b` and targeted repeat
`20260929T193341Z-a730fa05`

Ran all ten data scenarios once with baseline and the seven-tool hybrid. All
20 trials passed their semantic contracts and `marimo check`.

| Variant | Passed | Mean duration | Mean tools | Mean errors | Mean requests | Mean input | Mean output | Mean reasoning |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Baseline | 10/10 | 128.8s | 15.5 | 1.10 | 17.4 | 404,393 | 20,794 | 13,923 |
| Balanced hybrid | 10/10 | 124.8s | 17.7 | 0.60 | 18.2 | 693,830 | 21,019 | 13,597 |

Correctness was equal. The hybrid was 3.2% faster and had 45.5% fewer tool
errors, but used 14.2% more tools, 4.6% more model requests, 71.6% more input
tokens, and 1.1% more output tokens. Reasoning tokens were 2.3% lower. The
input regression was dominated by one high-cost long-retail trajectory.

| Length | Variant | Passed | Mean duration | Mean tools | Mean errors | Mean input |
|---|---|---:|---:|---:|---:|---:|
| Short | Baseline | 3/3 | 52.2s | 8.7 | 1.00 | 103,432 |
| Short | Hybrid | 3/3 | 44.3s | 8.7 | 0.67 | 57,885 |
| Medium | Baseline | 4/4 | 90.2s | 11.5 | 1.25 | 183,806 |
| Medium | Hybrid | 4/4 | 61.6s | 8.3 | 0.25 | 55,612 |
| Long | Baseline | 3/3 | 257.0s | 27.7 | 1.00 | 999,471 |
| Long | Hybrid | 3/3 | 289.3s | 39.3 | 1.00 | 2,180,731 |

The hybrid was strong on short and medium tasks: 15.1% and 31.7% faster, with
44.0% and 69.7% fewer input tokens respectively. The long aggregate moved in
the other direction: 12.6% slower, 42.2% more tools, and 118.2% more input
tokens.

| Scenario | Baseline duration / input | Hybrid duration / input | Result |
|---|---:|---:|---|
| Athletes prescribed | 74.8s / 138,135 | 36.4s / 40,948 | Both pass |
| Inventory inspection | 32.5s / 64,830 | 24.3s / 36,579 | Both pass |
| Support-ticket repair | 49.3s / 107,331 | 72.3s / 96,129 | Both pass |
| Retail short | 67.4s / 86,598 | 115.0s / 109,406 | Both pass |
| Dirty dates | 152.0s / 477,134 | 47.8s / 41,166 | Both pass |
| Missing dimensions | 87.6s / 88,116 | 45.7s / 49,433 | Both pass |
| Reactive repair | 53.9s / 83,376 | 38.0s / 22,443 | Both pass |
| Retail long | 359.7s / 1,205,474 | 513.5s / 4,197,342 | Both pass |
| SaaS reversal | 217.8s / 769,137 | 136.1s / 789,412 | Both pass |
| Operations context | 193.3s / 1,023,803 | 218.5s / 1,555,440 | Both pass |

Long retail was repeated because the hybrid's first run used 4.20 million
input tokens despite only two tool errors. The repeat reversed the expensive
trajectory: baseline took 475.3 seconds, 43 tools, and 2,514,869 input tokens;
hybrid took 246.8 seconds, 27 tools, zero errors, and 1,066,080 input tokens.

Across the two long-retail observations, both variants passed 2/2. Baseline
averaged 417.5 seconds, 36 tools, 1.5 errors, and 1,860,172 input tokens.
Hybrid averaged 380.1 seconds, 39.5 tools, one error, and 2,631,711 input
tokens. Hybrid was 9.0% faster but still used 41.5% more input tokens. This is
high trajectory variance, not a stable four-million-token cost, but the
remaining token difference is large enough to retain as a concern.

Replacing the breadth run's retail value with the two-run retail mean gives a
scenario-weighted sensitivity aggregate:

| Variant | Passed trials | Mean duration | Mean tools | Mean errors | Mean requests | Mean input | Mean output | Mean reasoning |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Baseline | 11/11 | 134.6s | 16.20 | 1.05 | 18.25 | 469,863 | 21,943 | 14,607 |
| Balanced hybrid | 11/11 | 111.4s | 16.45 | 0.50 | 17.05 | 537,267 | 18,307 | 11,662 |

Under this sensitivity view, the hybrid is 17.2% faster, uses 52.4% fewer
tool errors, 6.6% fewer requests, 16.6% fewer output tokens, and 20.2% fewer
reasoning tokens. It uses 1.5% more tools and 14.3% more input tokens. After
subtracting cache reads, the input regression is 8.4%, so repeated context is
most of the difference but not all of it.

Logfire recorded 153 baseline `execute_code` calls. Hybrid used 82
`execute_code`, 33 `apply_notebook_patch`, 33 `inspect_notebook`, 11
`configure_notebook`, 11 capability loads, four `run_cells`, two
`set_ui_value`, and one `manage_packages` call. The two UI calls occurred in
the expensive long-retail turn while validating a reactive scope toggle; the
model later removed that toggle after the requirement changed. The trajectory
also repeatedly verified and corrected visual cell ordering. This was useful
work taken too far, rather than a tool-error recovery loop.

All 52 turn traces in the full-suite run had exactly one root span and 8--46
connected spans.

Conclusion: the full suite confirms correctness breadth and strong short- and
medium-task efficiency. It weakens the simpler claim that the hybrid always
reduces tokens: long conversations can accumulate more repeated context when
the model performs many typed inspection and configuration cycles. Keep the
seven-tool hybrid as the leading architecture, but treat long-horizon context
growth and verification discipline as the next optimization target.

## Experiment 18: long-horizon payload and history optimization

Date: 2026-09-30

Model: `deepseek-ai/DeepSeek-V4.1-Flash`

Runs: control `20260929T195048Z-849cd2e9`, scoped inspection
`20260929T200126Z-c843abf2`, combined candidate
`20260929T200959Z-b005a301`, SaaS confirmation
`20260929T201410Z-d0a2d523`, and operations repeat
`20260929T201718Z-75dfe842`

Added artifact-level payload instrumentation before changing behavior. Every
turn now records raw request-history size, effective history size after
server-side compaction, full assistant-message size, and the input/output size
and error state of every tool call. Summary aggregates include totals and a
per-tool breakdown. Character counts are a stable payload proxy; provider
token usage remains the authoritative cost metric.

The fresh two-case control confirmed that notebook snapshots dominate tool
output. Across long retail and operations, `inspect_notebook` produced 180,367
of 242,971 tool-output characters (74.2%). Mutation postconditions were already
small: all 13 `apply_notebook_patch` returns totaled 4,488 characters (1.8% of
tool output). Patch *inputs*, not returns, were the other repeated source cost:
75,391 of 107,872 tool-input characters (69.9%). Therefore the proposed richer
automatic mutation representations were rejected. They would enlarge the
small side of the transcript and duplicate the existing execution summary.

Added three scopes to the existing inspection tool instead of another tool:

- `all` returns complete source and dependency metadata.
- `outline` omits source but retains IDs, status, dependencies, and source
  lengths.
- `errors` returns source only for failing or non-idle cells.

The hybrid instructions now treat a successful typed mutation and its
execution summary as a postcondition, prefer narrow inspection scopes, forbid
a full inspection used only as ritual verification, and tell the model to stop
once the request and necessary checks are satisfied.

The scoped-only run shows both the mechanism and the trajectory risk:

| Scenario | Control duration / input | Scoped duration / input | Control inspect output | Scoped inspect output |
|---|---:|---:|---:|---:|
| Retail investigation | 202.5s / 770,480 | 458.2s / 4,050,840 | 42,285 chars | 42,185 chars |
| Operations context | 547.7s / 3,104,216 | 337.6s / 1,813,313 | 138,082 chars | 5,412 chars |

Both runs passed. Operations used one full inspection, three error
inspections, and one outline inspection, reducing inspection output by 96.1%
and input tokens by 41.6%. Retail used the narrow scopes correctly but entered
an unrelated 64-tool trajectory with repeated live UI changes. Its 15
inspections still emitted about the same output as seven full control
inspections. The aggregate prompt-only result was worse, so prompt discipline
alone is not a reliable optimization. Keep the scopes because they provide
substantially better information density when selected; do not claim that the
prompt guarantees efficient planning.

Next added conservative server-side history compaction for the hybrid. It
keeps the immediately previous assistant turn, every exploratory result, and
every error verbatim. In older completed turns it:

- replaces successful full notebook inspection results with a short marker;
- replaces successful patch source with cell IDs, placement, and source
  lengths; and
- preserves tool-call IDs and result pairing, so the model history remains a
  valid tool transcript.

Current state remains recoverable from the live notebook. Compaction starts
only after two completed assistant turns, so the active loop and the most
recent user interaction are untouched.

The same retail and operations cases both passed with the combined candidate:

| Candidate | Passed | Mean duration | Mean tools | Mean errors | Mean requests | Mean input | Mean output | Mean reasoning |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Fresh control | 2/2 | 375.1s | 36.0 | 1.5 | 41.0 | 1,937,348 | 53,762 | 31,616 |
| Scoped only | 2/2 | 397.9s | 53.0 | 4.5 | 56.5 | 2,932,077 | 68,244 | 46,804 |
| Scoped + history | 2/2 | 226.1s | 29.5 | 1.5 | 33.0 | 1,161,583 | 38,995 | 26,922 |

Against the fresh control, the combined candidate was 39.7% faster, used
18.1% fewer tools, 19.5% fewer model requests, 40.0% fewer input tokens, 27.5%
fewer output tokens, and 14.8% fewer reasoning tokens with equal correctness
and errors. Retail landed near its good control trajectory (799,344 versus
770,480 input tokens), so the aggregate gain is not evidence that every
conversation becomes cheaper. Operations supplied the strong long-history
signal.

Operations was repeated once with the combined candidate. Both compacted
trials passed and averaged 196.5 seconds, 33 tools, one error, 36.5 requests,
and 1,149,358 input tokens. The scoped-only observation used 1,813,313 input
tokens; the untouched control used 3,104,216. The repeat itself used 774,895
input tokens and 166.2 seconds. This is still a small stochastic sample, but
two consecutive correct compacted trajectories both beat both non-compacted
observations.

The third six-turn case, SaaS requirement reversal, also passed with no tool
errors in 173.8 seconds and 678,523 input tokens. Experiment 17's un-compacted
observation was faster at 136.1 seconds but used 789,412 input tokens. This
supports the narrower conclusion: compaction consistently limits token growth,
but latency remains sensitive to the model's trajectory.

Decision:

- Keep payload instrumentation; it changed the design decision and makes
  future token regressions explainable.
- Keep scoped inspection as a backward-compatible extension of the existing
  tool. It can reduce snapshot output by orders of magnitude, but prompts are
  not sufficient to ensure the model chooses an efficient trajectory.
- Keep the conservative history compactor. It produced the clearest repeated
  long-conversation improvement while retaining recent state, exploration,
  failures, and valid tool-call pairing.
- Keep existing mutation postconditions unchanged. Do not add automatic rich
  representations or inspection-helper tools based on these results.
- Do not add caching of `execute_code`. Repeated calls often represent changed
  live state or deliberate exploration, and stale cached results would trade
  correctness for an unmeasured optimization.

Before enabling this by default outside the experimental hybrid, run a full
suite regression. Short and one-turn cases should be behaviorally unaffected
because compaction has no eligible history, but they still guard the shared
inspection schema. The focused second-model check below tests transcript
compatibility, while its efficiency result also identifies an important limit.

### Second-model boundary check

Model: `Qwen/Qwen3.5-35B-A3B`

Run: `20260929T202127Z-06d02565`

Ran the seven-turn operations case once after the DeepSeek decision. It passed
all semantic and source checks in 173.2 seconds, so the compacted transcript
retained enough information for a second model. It used 38 tools, 13 errors,
45 model requests, and 1,574,574 input tokens. This is worse than Experiment
16's un-compacted Qwen observation of 653,878 input tokens and does not support
an efficiency claim across models from one sample.

The artifact explains why: turns one through four used only six tools and no
errors. Turn five then used 24 tools, including repeated patch recovery, and
accounted for 932,286 input tokens and ten errors. Because that work happened
inside the active agent loop, no history processor could compact it safely.
Raw versus effective history differed by only 15,910 characters on the final
turn. This is evidence for a boundary rather than a compaction regression:
the strategy addresses repeated completed-turn state, not same-turn planning
or error-recovery loops. Keep the history processor, but treat bounded patch
recovery on weaker tool-use models as a separate future experiment.

## Experiment 19: optimized full-suite confirmation

Date: 2026-09-30

Model: `deepseek-ai/DeepSeek-V4.1-Flash`

Run: `20260930T014128Z-4ae81ab1`

Compared the production baseline with the optimized seven-tool hybrid across
all ten data scenarios. The candidate includes scoped inspection, verification
discipline, and conservative completed-turn history compaction. The runner used
four concurrent workers. All 20 trials passed their semantic contracts, source
contracts, and `marimo check`.

| Variant | Passed | Mean duration | Mean tools | Mean errors | Mean requests | Mean input | Mean output | Mean reasoning |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Baseline | 10/10 | 146.9s | 17.4 | 1.5 | 19.8 | 593,947 | 26,410 | 18,413 |
| Optimized hybrid | 10/10 | 82.9s | 12.7 | 0.4 | 13.9 | 215,648 | 12,602 | 8,010 |

With equal correctness, the optimized hybrid was 43.6% faster, used 27.0%
fewer tools, 73.3% fewer tool errors, 29.8% fewer model requests, 63.7% fewer
input tokens, 52.3% fewer output tokens, and 56.5% fewer reasoning tokens.
After subtracting cache reads, mean uncached input was 215,221 tokens for
baseline and 131,642 for hybrid, a 38.8% reduction. Every individual scenario
used fewer input tokens and completed faster with the hybrid in this run.

| Length | Variant | Passed | Mean duration | Mean tools | Mean errors | Mean input |
|---|---|---:|---:|---:|---:|---:|
| Short | Baseline | 3/3 | 35.9s | 7.3 | 1.00 | 71,650 |
| Short | Hybrid | 3/3 | 27.0s | 6.0 | 0.33 | 33,410 |
| Medium | Baseline | 4/4 | 88.2s | 13.0 | 2.00 | 198,647 |
| Medium | Hybrid | 4/4 | 52.1s | 7.5 | 0.25 | 52,317 |
| Long | Baseline | 3/3 | 336.1s | 33.3 | 1.33 | 1,643,311 |
| Long | Hybrid | 3/3 | 179.9s | 26.3 | 0.67 | 615,661 |

The hybrid reduced input tokens by 53.4% on short cases, 73.7% on medium
cases, and 62.5% on long cases. The long result directly resolves the concern
from Experiment 17, where the pre-optimization hybrid used more than twice the
baseline's long-case input because of one expensive retail trajectory.

| Scenario | Baseline duration / input | Hybrid duration / input | Result |
|---|---:|---:|---|
| Athletes prescribed | 25.3s / 69,738 | 23.9s / 36,411 | Both pass |
| Inventory inspection | 34.4s / 68,258 | 29.1s / 32,634 | Both pass |
| Support-ticket repair | 48.1s / 76,954 | 28.1s / 31,186 | Both pass |
| Retail short | 127.1s / 291,910 | 90.6s / 96,717 | Both pass |
| Dirty dates | 94.6s / 259,546 | 32.1s / 21,712 | Both pass |
| Missing dimensions | 70.8s / 118,119 | 57.0s / 63,778 | Both pass |
| Reactive repair | 60.2s / 125,012 | 28.6s / 27,060 | Both pass |
| Retail long | 381.0s / 1,904,470 | 252.6s / 956,223 | Both pass |
| SaaS reversal | 362.4s / 1,457,885 | 158.2s / 386,500 | Both pass |
| Operations context | 265.0s / 1,567,578 | 129.1s / 504,260 | Both pass |

The optimized hybrid used 61 exploratory executions, 29 atomic patches, 21
inspections, nine capability loads, five configuration calls, and two explicit
cell runs. It never selected package or UI-state tools in data tasks where they
were irrelevant. Baseline used 172 exploratory executions.

History compaction reduced the hybrid's accumulated raw long-case history from
1,233,604 to 1,130,601 characters (8.3%) and reduced mean final long-case
history from 125,544 to 109,369 characters (12.9%). Those direct reductions
are useful but smaller than the token improvement against baseline. The full
gain belongs to the combined strategy: typed mutations, fewer recovery calls,
narrower inspections, verification discipline, compaction, and stochastic
trajectory differences. It should not be attributed to compaction alone.

Logfire contained 52 turn traces for the run. Each trace contained 6--40
spans, exactly one root span, and zero child spans whose parent was unavailable.

This is one observation per scenario, and four-way parallel execution makes
absolute latency sensitive to endpoint contention. Exact percentages are not
population estimates. Token counts are less affected by concurrency, and the
direction is unusually consistent: equal correctness and lower input in every
scenario, supported by the repeated long-case experiments above.

Conclusion: the optimized seven-tool hybrid is now the best demonstrated
strategy and has passed the requested full-suite gate. Keep it as the leading
architecture. The next optimization target should not be more history work or
more tools; it should be bounded same-turn recovery for models that repeatedly
submit failing patches, measured separately on the Qwen failure-heavy case.

## Experiment 20: patch ambiguity and same-turn recovery

Date: 2026-09-30

Models: `Qwen/Qwen3.5-35B-A3B` and
`deepseek-ai/DeepSeek-V4.1-Flash`

Runs: original Qwen failure-heavy observation
`20260929T202127Z-06d02565`, explicit patch schema
`20260930T015528Z-d7f628df`, schema plus focused guidance
`20260930T020123Z-2dda4f16`, and DeepSeek regression
`20260930T015831Z-594c90bc`

Inspected Qwen's 24-tool turn in Logfire before adding a retry policy. The
first seven large patch failures had the same cause: the model supplied
invented names such as `cell_join_cardinality` in `cell_id` for cells it
intended to create. The old patch item represented both operations with one
optional field: a present `cell_id` meant replacement and an omitted one meant
insertion. The tool returned the exact available stable ID and the hybrid skill
already said to omit IDs for new cells, but Qwen repeatedly reconstructed the
same ambiguous object incorrectly.

Changed the single atomic patch tool without adding another tool:

- `replacements` accepts complete source plus a required existing stable ID.
- `insertions` accepts complete source plus an optional existing
  `after_cell_id`; it cannot accept a caller-created ID.
- `delete_cell_ids` remains unchanged.

The implementation still compiles all three groups into one existing
`_code_mode` transaction and one reactive execution batch. Historical
compaction understands both the old and new argument shapes so conversations
created before the schema change remain compactable.

| Qwen candidate | Passed | Duration | Tools | Errors | Requests | Input | Output |
|---|---:|---:|---:|---:|---:|---:|---:|
| Optional `cell_id` | Yes | 173.2s | 38 | 13 | 45 | 1,574,574 | 28,245 |
| Explicit insert/replace | Yes | 140.1s | 38 | 11 | 46 | 927,035 | 24,718 |
| Explicit schema + guidance | Yes | 117.1s | 27 | 12 | 34 | 717,989 | 18,736 |

The explicit schema reduced input by 41.1% while preserving correctness. Tool
count did not initially fall because Qwen then inserted cells incrementally and
hit genuine marimo graph validation: public loop targets such as `region`,
`status`, and `count` were defined in multiple cells. Added local guidance to
batch coherent insertions in one patch and to prefix top-level loop,
context-manager, and exception targets with `_`. With both changes, input was
54.4% below the original observation, duration was 32.4% lower, tools were
28.9% lower, requests were 24.4% lower, and output was 33.7% lower.

Errors remained high and moved between turns. The final guided Qwen turn made
nine calls with seven errors, recovered, and the scenario passed. This is
direct counterevidence to a blind per-turn error budget: a cap below eight
would have converted a correct result into a failure. Error count alone does
not distinguish a productive correction sequence from a repeated strategy.
Do not add a hard retry cutoff without a semantic repeated-failure detector or
a resumable fallback.

Ran focused DeepSeek regressions after the schema and guidance change:

| Scenario | Passed | Duration | Tools | Errors | Input |
|---|---:|---:|---:|---:|---:|
| Athletes prescribed | Yes | 38.3s | 7 | 0 | 36,651 |
| Retail short | Yes | 44.6s | 9 | 1 | 62,135 |
| Operations context | Yes | 160.2s | 32 | 0 | 772,384 |

All three passed. Operations had zero errors and its input was effectively the
same as the earlier 774,895-token compacted repeat, although higher than the
particularly cheap 504,260-token full-suite trajectory. This is consistent
with model variance rather than a clear regression.

Conclusion: keep the explicit patch groups and focused naming/batching
guidance. They address observed, generalizable interface ambiguity while
preserving atomicity and the seven-tool budget. Reject a blind retry cap. The
remaining Qwen errors are primarily notebook-graph design mistakes inside a
complex generation turn; improving recovery further requires classifying
repeated failure signatures and supplying targeted corrective guidance, not
silently stopping or adding more editor tools.

## Experiment 21: frozen holdout generalization

Date: 2026-09-30

Model: `deepseek-ai/DeepSeek-V4.1-Flash`

Run: `20260930T022200Z-a2e2f948`

Created a separate four-case holdout before running either variant. The cases
targeted risks not represented in the development suite:

- restoring an exact implementation inspected before five intervening turns;
- repairing and extending a 26-cell reactive graph;
- combining package management, a live UI update, a source edit, and cell
  configuration in one task;
- delaying mutation through an ambiguous request and retaining requirements
  across explanation-only turns.

The current runner cannot faithfully simulate a human editing the live
notebook between chat turns or grade screenshots, so those proposed holdouts
remain future work. Disk rewrites were deliberately not used as a substitute
for a real live-editor mutation.

The first frozen run reported baseline 2/4 and hybrid 1/4. Audit found that
three failures came from invalid grader assumptions, not incorrect notebooks:

- the expected bounded mean was entered as `46.833`; the fixture's original
  calculation is `46.333`, which both variants restored;
- the graph contract accepted only an assignment to
  `checkpoints["stage_24"]`, rejecting the hybrid's equivalent dictionary
  literal entry;
- the package contract required `from eval_scaler import scaled_total`,
  rejecting the valid `import eval_scaler` form used by both variants.

Corrected the arithmetic and changed the two syntax-specific checks to
semantic source patterns. Regrading the saved final notebooks, without model
reruns or strategy changes, gives 4/4 for both variants. The raw result remains
in the run artifact and is part of the benchmark provenance. The scenario hash
was also strengthened before this run: it now includes the complete source
files that define fixtures and contracts, not only prompts and setup-function
bodies.

| Variant | Adjudicated pass | Mean duration | Mean tools | Mean errors | Mean requests | Mean input | Mean output | Mean reasoning |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Baseline | 4/4 | 103.4s | 17.75 | 2.25 | 21.50 | 370,981 | 16,356 | 10,906 |
| Hybrid | 4/4 | 90.7s | 17.25 | 1.75 | 19.25 | 384,805 | 12,638 | 8,039 |

With equal corrected correctness, the hybrid was 12.3% faster, used 2.8%
fewer tools, 22.2% fewer tool errors, 10.5% fewer model requests, 22.7% fewer
output tokens, and 26.3% fewer reasoning tokens. Unlike the development-suite
run, total input increased by 3.7%. After subtracting cache reads, mean
uncached input increased from 146,629 to 172,005 tokens, or 17.3%. This is a
real warning against generalizing Experiment 19's exact efficiency gains.

| Scenario | Baseline duration / input | Hybrid duration / input | Adjudicated result |
|---|---:|---:|---|
| Historical exact restore | 121.7s / 497,064 | 145.0s / 948,327 | Both pass |
| Large reactive graph | 50.0s / 129,711 | 14.3s / 51,770 | Both pass |
| Mixed editor capabilities | 101.7s / 403,818 | 57.1s / 166,964 | Both pass |
| Campaign clarification | 140.1s / 453,331 | 146.4s / 372,160 | Both pass |

The hybrid generalized strongly on structure and tool selection. It repaired
the 26-cell graph with 60.1% fewer input tokens and 71.4% less time. It used
the intended typed package, UI, configuration, inspection, patch, and run
operations in the combined capability case, reducing input by 58.7% and time
by 43.9%. Both variants correctly avoided tools on the explicit
explanation-only campaign turn. On the historical case, the hybrid also used
zero tools on both explanation-only turns, while the baseline made one
exploratory call on each.

The historical restore exposed the principal weakness. Conservative history
compaction removed the literal first-turn inspection. On the final turn, the
hybrid explicitly reported that the inspection had been compacted, searched
the current notebook, session cache, server log, sibling temporary
directories, and finally the entire temporary directory tree for a previous
copy. One directory listing returned 193,036 characters and another search
returned 42,191 characters. That final turn consumed 799,143 input tokens and
ten tool calls, compared with baseline's 121,737 input tokens and three calls.
The model still reconstructed the correct algorithm, constants, label, and
rounding because its earlier natural-language response had restated those
details. It could not restore byte-identical source and correctly disclosed
that limitation.

This is not evidence to discard compaction: excluding the historical-restore
case, hybrid input was 40.1% lower and duration was 25.3% lower across the
other three holdouts. It is evidence that conversation history is not a
version-control system. Exact restoration needs notebook revision storage and
a narrow way to retrieve a prior cell revision; retaining every old tool
payload indefinitely would trade correctness in one workflow for unbounded
cost in ordinary long conversations.

Logfire contained 32 turn traces for the run, each with 4--38 spans, exactly
one root, and no unavailable parent spans. The anomalous restore trajectory
was verified directly from trace `335413f0e0d7694cd198e5728d6dddcc`.

Conclusion: the seven-tool hybrid generalizes beyond the development cases,
especially to large graphs and mixed editor operations, but the holdout
invalidates any claim that it is uniformly cheaper. Freeze these cases as a
regression suite now that they have been observed. The next architecture
experiment should be revision-aware restoration, not another prompt tweak or
broader unstructured filesystem access. A second independent holdout and
additional models are still required before estimating production win rates.

## Experiment 22: live human edit and static-image holdouts

Date: 2026-09-30

Runs: DeepSeek live edit `20260930T030403Z-e42ff843`; Qwen static image
`20260930T030707Z-78990e7e`

Added the two holdouts deferred from Experiment 21.

The live-edit runner sends a replacement through `/api/kernel/run`, the same
endpoint used by the editor to run changed cell code, between chat turns. It
waits for `/api/kernel/status` to return to idle before sending the next user
message. A model-free integration check confirmed that the active kernel
changed from `paid-only / 300` to `paid-and-settled / 450` without modifying
the notebook file.

The visual runner attaches a deterministic 14,526-byte PNG as a Vercel
`FileUIPart` in the user message. The prompt does not repeat the corrections;
the image says to sort bars high-to-low, rotate labels to -35 degrees, and
widen the chart to 650 pixels. This avoids frontend and Playwright variance
while exercising the same image attachment format as the chat sidebar. Qwen
3.5 35B A3B was selected because [W&B lists it as a multimodal
model](https://site.wandb.ai/inference/).

### Live human edit

Model: `deepseek-ai/DeepSeek-V4.1-Flash`

| Variant | Passed | Duration | Tools | Errors | Requests | Input | Output | Reasoning |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Baseline | Yes | 160.4s | 37 | 8 | 39 | 846,672 | 22,416 | 15,184 |
| Hybrid | Yes | 108.8s | 21 | 1 | 20 | 229,097 | 15,817 | 13,017 |

Both variants respected the out-of-band policy change and finished with
`revenue_policy='paid-and-settled'`, total revenue `450`, and top region
`East`. The hybrid used 72.9% fewer input tokens, 43.2% fewer tools, 87.5%
fewer tool errors, and 48.7% fewer model requests; it was 32.2% faster.

The intervention also exposed a real consistency boundary. `/api/kernel/run`
updated the executing kernel, but the unsaved notebook document and disk file
still contained the prior source. Both agents initially saw stale source while
the live globals contained the new policy. Re-running the stale policy cell
temporarily reverted the runtime value. Both eventually treated the user's
live value as authoritative, rewrote the policy source, and saved a coherent
notebook.

This case represents the important race where a user has run an edit but it
has not yet autosaved. It should remain in the suite. A later scenario can
separately model a completed edit-plus-save transaction. The harness would
benefit from an inspection result that explicitly reports document/runtime
divergence instead of forcing filesystem and session-cache exploration.

### Static visual review

Model: `Qwen/Qwen3.5-35B-A3B`

The first run reported both variants as failures. Audit found the baseline had
implemented a valid descending sort by pre-sorting the DataFrame, while the
grader accepted only Altair's `sort="-y"` spelling. Corrected the source
contract to accept both semantic forms and regraded the saved notebook without
rerunning the model.

| Variant | Adjudicated result | Duration | Tools | Errors | Requests | Input | Output |
|---|---:|---:|---:|---:|---:|---:|---:|
| Baseline | Pass | 25.0s | 15 | 4 | 16 | 141,556 | 2,525 |
| Hybrid | Fail | 15.4s | 8 | 4 | 9 | 51,734 | 1,352 |

Both variants demonstrably read the attachment: each independently repeated
all three image-only corrections before editing. The baseline applied all
three, preserved the chart display expression, executed the notebook, and
preserved `analysis_summary`.

The hybrid failure was genuine. It first tried an invalid `transform_sort`,
then changed the encoding to `sort="revenue"` rather than a descending sort,
and removed the trailing `chart` display expression. It also left the summary
cell unexecuted, so final live-kernel grading could not find
`analysis_summary`. Despite this, its final response claimed the notebook was
error-free and verified. The result identifies a verification failure rather
than a multimodal transport failure.

The result is one Qwen observation and should not be read as a general claim
that the baseline handles images better. It does show that the seven-tool
hybrid's successful mutation postcondition is insufficient evidence of
task-level success: a patch can execute while removing the requested visual
output or leaving an unrelated required cell stale. Visual tasks need a final
check that the target cell still produces a rendered output, followed by a
task-level summary check.

Logfire contained six turn traces across the two runs, each with 19--54 spans,
exactly one root, and no unavailable parent spans.

Conclusion: the remaining holdout infrastructure works. Keep the unsaved
live-edit race and static-image case as regression tests. The next harness
work suggested by these results is not another tool: expose live
document/runtime divergence during inspection and strengthen final
verification to confirm requested outputs remain rendered and headline cells
are live.

## Experiment 23: anomaly-only output verification

Date: 2026-09-30

Models: `Qwen/Qwen3.5-35B-A3B` and
`deepseek-ai/DeepSeek-V4.1-Flash`

Runs: Qwen warning prototype `20260930T041706Z-59306cda`; Qwen revised
candidate `20260930T041944Z-458a8d24` and
`20260930T042022Z-6e7ab937`; DeepSeek nonvisual control
`20260930T042105Z-5d917ebd`

Experiment 22 showed that a successful patch and error-free cells do not prove
that a requested visual result is correct. The first prototype compared every
cell's pre/post runtime status and returned warnings for new problems plus lost
output. This duplicated the exact runtime diagnostics already present in a
failed tool result. It added no useful evidence and was removed.

The revised candidate keeps successful patch output unchanged. It emits a
warning only when an edited cell previously had rich output or ended in a
display expression and the replacement loses that behavior. This source-level
check also works when the initial notebook has not executed and therefore has
no captured runtime output. The hybrid completion guidance now distinguishes
runtime health from semantic correctness and asks the model to inspect the
live object or serialized specification for rich-output behavior that
execution alone cannot establish.

The first warning prototype remained mixed on the visual case:

| Candidate | Passed | Mean duration | Mean tools | Mean errors | Mean requests | Mean input | Mean output |
|---|---:|---:|---:|---:|---:|---:|---:|
| Original hybrid, Experiment 22 | 0/1 | 15.4s | 8.00 | 4.00 | 9.00 | 51,734 | 1,352 |
| Broad status warnings | 1/2 | 18.3s | 7.00 | 1.00 | 8.00 | 41,678 | 1,346 |
| Sparse warning + semantic guidance | 4/4 | 13.8s | 6.25 | 1.75 | 7.25 | 37,006 | 1,102 |

All four revised trials applied the descending sort, `labelAngle=-35`, width
650, preserved the trailing chart display expression, kept
`analysis_summary` live, and passed `marimo check`. Compared with the original
failed observation, the four-run mean used 21.9% fewer tools, 56.3% fewer tool
errors, 19.4% fewer requests, and 28.5% fewer input tokens. These percentages
compare different sample sizes and are directional rather than population
estimates.

Trace inspection limits the causal claim. No lost-output warning fired in the
four revised trials because every first patch preserved the display
expression. Both trials in the first revised pair generated the correct
descending dataframe before any semantic check. One later tried to inspect
`chart.spec`, which is not an Altair API and raised `AttributeError`; the other
only checked for cell errors. Therefore the 4/4 result supports the combined
candidate but does not prove that the warning caused the improvement. The
concise instruction may have improved initial planning, and ordinary model
variance remains plausible.

Two nonvisual DeepSeek controls both passed:

| Scenario | Current duration / tools / input | Experiment 19 duration / input |
|---|---:|---:|
| Retail short | 94.9s / 9 / 58,633 | 90.6s / 96,717 |
| Reactive repair | 42.5s / 6 / 42,514 | 28.6s / 27,060 |

The controls are mixed but show no runaway verification loop. Retail duration
was close while input fell; reactive repair was slower and used more input
than its prior single observation. More nonvisual repetitions would be needed
to estimate a small prompt-level regression, but the current evidence does not
justify another broad suite.

Every visual trial exposed a separate execution-order issue: the atomic patch
queued initially stale import, data, chart, and summary cells together, but
the first execution frequently ran the data cell before its `pandas` import
was live. The exact `NameError` allowed recovery through `run_cells`, but this
accounted for at least one avoidable error and model request per trial. Fixing
dependency-ordered initial execution is a clearer next optimization than
adding more verification output.

Logfire contained eight trial traces for this experiment, with 12--22 spans
each. Every trace had exactly one root and zero unavailable parents.

Conclusion: reject broad notebook-health reporting as duplicate transcript
bloat. Retain the concise semantic-verification guidance and the sparse
lost-visible-output warning as a regression signal. Treat the visual task as
a regression case, not an unseen holdout, and do not claim that arbitrary user
semantics are automatically verified.

## Experiment 24: register document-only cells before atomic execution

Date: 2026-09-30

Models: `Qwen/Qwen3.5-35B-A3B` and
`deepseek-ai/DeepSeek-V4.1-Flash`

Runs: Qwen visual confirmation `20260930T043650Z-d372fd79`; DeepSeek
nonvisual control `20260930T043738Z-b323d2c8`

Every visual trial in Experiment 23 initially failed with `NameError: pd is
not defined`. The patch tool correctly requested all initially stale cells,
but `_code_mode` filtered unchanged cells that existed in the notebook
document but had not yet entered the kernel graph. The data cell was
registered because it was edited; its unchanged import ancestor was not.
Without that graph node, dependency sorting could not order the import first.

The fix registers explicitly requested document-only cells in the same graph
mutation as edited cells. The existing scheduler then performs the normal
topological ordering. A focused regression test reproduces the prior failure
with an unchanged `import math` ancestor and an edited document-only consumer;
it failed before the change and passes afterward. The full code-mode context
and hybrid-tool selection ran 87 tests successfully.

Two fresh visual trials both passed with a successful first atomic patch and
no recovery call:

| Candidate | Passed | Mean duration | Mean tools | Mean errors | Mean requests | Mean input | Mean output |
|---|---:|---:|---:|---:|---:|---:|---:|
| Before registration fix, Experiment 23 | 4/4 | 13.8s | 6.25 | 1.75 | 7.25 | 37,006 | 1,102 |
| After registration fix | 2/2 | 11.6s | 3.50 | 0.00 | 4.50 | 19,115 | 680 |

The post-fix observations used 44.0% fewer tools, 37.9% fewer requests, 48.3%
fewer input tokens, and no tool errors. Both patch spans returned
`success=true`, empty `stderr`, and empty error lists. Neither trajectory used
`run_cells`. One trial verified the result by evaluating `chart` directly;
marimo's rich representation returned the complete Vega-Lite specification,
including the ordered data, `labelAngle=-35`, and width 650. This supports
direct live-object inspection as the general semantic-verification primitive.

The nonvisual reactive-repair control also passed with zero tool errors, seven
tools, and 59,673 input tokens. Its 68.8-second duration and token use were
higher than the immediately preceding single observation, so the run supports
correctness and error elimination but not a broad latency claim.

Conclusion: retain the runtime fix. It removes a deterministic recovery cause
at the transaction layer, applies to arbitrary initially unexecuted notebooks,
and does not add tools, prompts, or model-visible output.

## Experiment 25: explicit document/runtime source divergence

Date: 2026-09-30

Model: `deepseek-ai/DeepSeek-V4.1-Flash`

Run: `20260930T044020Z-676c031e`

The live-human-edit holdout previously forced agents to reconcile stale
document source with newer kernel values indirectly. Inspection now adds
fields only when the notebook document and executing graph disagree:
`source_diverged=true`, `runtime_code_chars`, and `runtime_code` for
source-bearing scopes. Ordinary synchronized cells receive no additional
fields. Outline inspection reports only the divergence flag and length.

The hybrid guidance treats `runtime_code` as the current human edit and asks
the model to preserve it while synchronizing durable source through the typed
patch tool. One fresh two-turn trial passed:

| Hybrid | Passed | Duration | Tools | Errors | Requests | Input | Output |
|---|---:|---:|---:|---:|---:|---:|---:|
| Experiment 22 | Yes | 108.8s | 21 | 1 | 20 | 229,097 | 15,817 |
| Explicit divergence | Yes | 28.8s | 8 | 0 | 9 | 51,281 | 3,456 |

The revised trajectory was 73.5% faster, used 61.9% fewer tools, eliminated
the tool error, used 55.0% fewer model requests, and used 77.6% fewer input
tokens. This is one comparison against one prior observation, so exact
percentages are directional.

The second-turn trace validates the mechanism. Its first inspection reported
the document's `paid-only` policy beside the exact live
`paid-and-settled` runtime source. The next call copied that runtime code into
the policy replacement, updated `analysis_summary`, and returned a successful
atomic patch with empty errors. One exploratory call then verified policy,
total revenue 450, and top region `East`. There was no filesystem search,
session-cache search, or stale-source rerun.

Conclusion: retain divergence reporting. It is sparse, describes a general
notebook consistency condition rather than a benchmark-specific value, and
turns an ambiguous state-recovery problem into a direct synchronization task.

## Experiment 26: bounded revision-aware restoration

Date: 2026-09-30

Models: `deepseek-ai/DeepSeek-V4.1-Flash` and `Qwen/Qwen3.5-35B-A3B`

Runs: DeepSeek `20260930T044537Z-784f4bcf`; Qwen reconstruction
`20260930T044803Z-91f8bcf0`; rejected availability cue
`20260930T044940Z-9842605c`; Qwen explicit restoration rule
`20260930T045048Z-bec7e052`

Experiment 21 showed that compacted conversation history is not a reliable
source archive. The historical restore passed semantically only after the
hybrid searched session state and temporary directories, consumed 948,327
input tokens over the conversation, and reconstructed rather than recovered
the original source.

The candidate stores source replaced or deleted by agent-authored notebook
mutations in existing per-kernel agent state. History is deduplicated and
bounded to ten revisions per cell, 100 revisions per kernel, and 200,000
aggregate source characters. Oldest revisions are evicted globally, and
explicit history output reports when truncation occurred. It does not record
ordinary human edits or add information to normal inspection results. The
existing `inspect_notebook` tool exposes the archive only through an explicit
`scope="history"` request, returning a flat chronological list with sequence,
cell ID, name, and source. This avoids adding another tool to the model's tool
selection problem.

The fresh DeepSeek historical holdout passed all semantic and source checks:

| Hybrid | Passed | Duration | Tools | Errors | Requests | Input | Output |
|---|---:|---:|---:|---:|---:|---:|---:|
| Experiment 21 | Yes | 145.0s | 23 | 4 | 27 | 948,327 | 16,229 |
| Revision-aware | Yes | 65.7s | 14 | 0 | 17 | 166,665 | 8,071 |

The new observation was 54.7% faster, used 39.1% fewer tools, eliminated all
four tool errors, used 37.0% fewer model requests, and used 82.4% fewer input
tokens. These percentages compare one run with one prior run and are
directional, not variance estimates.

The final-turn trace validates the intended mechanism. The first call was
`inspect_notebook(scope="history")`, which returned the original bounded-mean
cell source. The next call used that source verbatim in one atomic replacement
and deleted the later median table. One exploratory call verified the values
and absence of median-only globals, and a compact outline confirmed the final
two-cell graph. There was no filesystem, session-cache, or temporary-directory
search. The trace had one root span and every child had an available parent.

Cross-model testing exposed a discoverability failure. The first Qwen run
passed the old semantic contract but never called history; it reconstructed an
equivalent bounded mean with different source. A sparse
`restorable_revision_count` field did not help because the model mutated before
performing normal inspection, and that field was removed as output bloat. An
explicit rule—undo, revert, and exact restoration must start with history and
must not reconstruct from prose—made history the first final-turn call. Qwen
then copied the exact stored source in one patch and passed in 31.9 seconds
with 10 tools, two errors, 17 requests, 98,664 input tokens, and 3,686 output
tokens. Its final trace had one root and connected children.

The grader now parses the saved marimo notebook and requires the complete
metric cell body to equal the original source. Regrading the saved artifacts
correctly rejects Qwen's semantically equivalent reconstruction and accepts
the history-based restoration. This closes the gap between the scenario name
and its automated contract.

The focused benchmark, revision, code-mode context, and hybrid-tool suites
pass 123 tests; the changed production files pass Ruff and mypy.

Conclusion: retain the bounded revision store and explicit history scope. It
solves a general undo/restore requirement without retaining unbounded chat
history, expanding the tool count, or bloating ordinary inspection. The next
valuable work is broader regression coverage, not another prompt tweak or a
separate restore tool.

## Experiment 27: multi-revision and deleted-cell regression

Date: 2026-09-30

Models: `deepseek-ai/DeepSeek-V4.1-Flash` and `Qwen/Qwen3.5-35B-A3B`

Runs: Qwen `20260930T050209Z-df0e7e80`; DeepSeek initial
`20260930T050210Z-ebb203a2`; DeepSeek private-name guidance
`20260930T050401Z-17cb4604`

Added a dedicated `regression` suite for cases derived from observed failures,
separate from the frozen holdout suite. Its first case makes two successive
changes to the same metric cell, deletes an independent audit cell, includes a
non-editing explanation turn, and then requires the oldest metric revision and
the deleted audit source to be restored exactly. The final grader compares both
complete cell bodies rather than semantic fragments.

Both models passed on the first regression run:

| Model | Duration | Tools | Errors | Requests | Input | Output |
|---|---:|---:|---:|---:|---:|---:|
| Qwen | 27.0s | 8 | 0 | 13 | 60,868 | 3,695 |
| DeepSeek | 57.1s | 13 | 1 | 18 | 127,197 | 6,301 |

Both final turns called `inspect_notebook(scope="history")` first. History
contained three ordered records: the original metric, the deleted audit cell,
and the intermediate median metric. Each model selected the first two, used
one atomic patch to replace the current metric and insert the deleted audit
source, and passed both exact-cell checks. This verifies retrieval across
multiple revisions of one stable cell and recreation of a deleted cell with a
new server-generated ID.

DeepSeek's single error came from exploratory verification after the correct
patch. It tried to read `_bounded_scores` from the scratchpad, but marimo
private names are cell-scoped and are intentionally renamed. Added one sentence
to the exploratory tool description: private `_` names cannot be read there;
verify public outputs or recompute the intermediate. A repeat still passed and
removed the error:

| DeepSeek | Duration | Tools | Errors | Requests | Input | Output |
|---|---:|---:|---:|---:|---:|---:|
| Before guidance | 57.1s | 13 | 1 | 18 | 127,197 | 6,301 |
| After guidance | 43.9s | 11 | 0 | 15 | 120,500 | 6,920 |

The repeat was 23.1% faster, used two fewer tools and three fewer model
requests, and eliminated the private-name recovery. Input fell 5.3% while
output rose 9.8%; one pair is directional evidence only. Trace inspection
confirmed no private-name access in the repeat's restoration turn. The Qwen
and final DeepSeek restoration traces each contained 12 spans, exactly one
root, and no missing parents.

The experiment also corrected exact-source check reporting: successful checks
now say `exact cell source matched` instead of displaying the failure-oriented
`was not found` reason.

Conclusion: keep the regression suite, exact multi-cell contracts, and concise
private-name guidance. The revision design handles the two principal restore
shapes without a new tool. Further regression additions should come from new
observed failures rather than synthetic permutations of the same workflow.

## Experiment 28: current-branch broad regression gate

Date: 2026-09-30

Models: `deepseek-ai/DeepSeek-V4.1-Flash` and `Qwen/Qwen3.5-35B-A3B`

Runs: hybrid data suite `20260930T050908Z-34cebf27`; unchanged orders
retry `20260930T051436Z-8054ac59`; capabilities
`20260930T051438Z-0b632efd`; text holdouts
`20260930T051528Z-ebc77425`; visual holdout
`20260930T051530Z-293eaf6b`; fresh baseline data suite
`20260930T051933Z-03335fdd`; clarified orders hybrid
`20260930T052712Z-c9486e81`; clarified orders baseline
`20260930T052720Z-bfc7d204`

Reran the accumulated current branch across the ten data scenarios, all three
capability scenarios, all six holdouts, and a fresh paired baseline. The data
suites used four concurrent workers. Capability and text-holdout concurrency
was capped so no more than four real-model trials ran at once.

The raw current-branch data comparison was:

| Variant | Passed | Mean duration | Mean tools | Mean errors | Mean requests | Mean input | Mean output | Mean reasoning |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Baseline | 10/10 | 108.6s | 16.8 | 1.10 | 18.7 | 482,003 | 20,726 | 14,357 |
| Current hybrid | 9/10 | 92.4s | 15.3 | 0.70 | 16.5 | 408,899 | 18,612 | 12,375 |

The hybrid was 14.9% faster, used 8.9% fewer tools, 36.4% fewer tool errors,
11.8% fewer model requests, 15.2% fewer input tokens, 10.2% fewer output
tokens, and 13.8% fewer reasoning tokens. These are contemporaneous runs, but
one observation per scenario and concurrent execution still make the effect
sizes directional.

The hybrid's raw miss was `orders_missing_dimensions`. With no tool errors, it
created a documented sample dataset rather than loading the fixture. The
scenario prompt said only “Analyze products and orders” and did not name
`data/products.csv` or `data/orders.csv`; its calculations were internally
correct for the invented data. The same unchanged hybrid scenario passed on
immediate retry. Corrected the benchmark instruction to name both fixture
paths and added a contract test. Both variants then passed, with the following
single-case trajectories:

| Clarified orders | Duration | Tools | Errors | Requests | Input | Output |
|---|---:|---:|---:|---:|---:|---:|
| Hybrid | 48.8s | 8 | 0 | 7 | 51,566 | 8,477 |
| Baseline | 173.4s | 27 | 4 | 26 | 742,141 | 26,302 |

The correction means the intended data behavior passes for both strategies,
but it does not erase the hybrid's initial first-attempt miss. Treat the raw
9/10 versus 10/10 result as reliability evidence and the clarified pair as
evidence that the miss came from benchmark ambiguity rather than an inability
to solve the task.

Every broader editor surface passed:

| Suite | Model | Passed | Mean duration | Mean tools | Mean errors | Mean input |
|---|---|---:|---:|---:|---:|---:|
| Capabilities | DeepSeek | 3/3 | 20.0s | 9.0 | 0.67 | 101,584 |
| Text holdouts | DeepSeek | 5/5 | 65.7s | 12.4 | 0.80 | 203,278 |
| Visual holdout | Qwen | 1/1 | 8.2s | 3.0 | 0.00 | 16,895 |

The text holdouts include exact historical restoration, the 26-cell graph,
mixed package/UI/configuration operations, delayed clarification, and an
out-of-band live edit. The visual case applied all image-only chart
requirements with one patch and no errors. Together with Experiment 27's
multi-revision regression, every current scenario has a passing current-hybrid
observation.

Token efficiency is weaker than the unusually cheap Experiment 19 hybrid run
(215,648 mean input) but remains better than the fresh baseline. The long data
cases account for nearly all of the variance: current hybrid mean input was
1,254,223 versus 1,643,311 in the older baseline comparison and 615,661 in the
best prior hybrid observation. This reinforces that single-run token deltas
are noisy even when architecture and correctness are stable.

Logfire contained 77 traces across the broad hybrid and baseline runs audited
here. Every trace had exactly one root span and no child with a missing parent.

Conclusion: the seven-tool hybrid remains the best demonstrated architecture.
It is broadly correct and still more efficient than a fresh baseline across
the main data suite, while handling editor capabilities that baseline code mode
does not express directly. The result is not an unconditional dominance claim:
the initial 9/10 hybrid result and token variance justify retaining repeated
critical cases and reporting confidence intervals once the harness supports
enough repetitions.

## Experiment 29: Generate with AI and inline-completion foundations

Date: 2026-09-30

Models: `deepseek-ai/DeepSeek-V4.1-Flash` and `Qwen/Qwen3.5-35B-A3B`

Runs: corrected DeepSeek Generate
`20260930T071817Z-ad0f0606`; DeepSeek inline
`20260930T071217Z-48d2fed2`; Qwen Generate
`20260930T071547Z-5e85f387`; Qwen inline
`20260930T071542Z-95105ba2`; repeated cross-model inline
`20260930T071741Z-dc205b94`; Qwen 2,048-token probe
`20260930T072010Z-db7da58c`; Qwen template-thinking fix
`20260930T073135Z-a4269f65`; three-repetition confirmation
`20260930T073156Z-cf9ff925`

Added production-path suites for the two editor AI surfaces that were not
covered by the code-mode benchmark. Generate trials call
`/api/ai/completion`, consume the structured multi-cell stream, execute Python
cells in order, and grade the resulting summary. Inline trials call
`/api/ai/inline_completion`, apply the editor's exact prefix/suffix cleanup,
compose the candidate source, and grade syntax and behavior. Each suite starts
with one short, one medium, and one long case.

The runner now accepts repeated `--model` arguments. Model-qualified trial IDs
and artifact paths prevent cross-model collisions. Summaries group scenarios
and variants per model and report Wilson pass-rate intervals plus duration and
input-token confidence intervals. HTTP failures retain the server detail and
trace ID. The production APIs do not expose a deterministic sampling seed, so
the runner uses honest independent repetitions instead of a nonfunctional
seed flag.

Two defects in the first Generate draft were corrected before comparison. A
substring check incorrectly treated `paid_orders =` as a redefinition of
`orders`; the contract now uses anchored regular expressions. The sales prompt
also requested “net revenue” without defining it, so it now states `gross -
returns`. File-based Generate cases now provide column schemas through the
existing completion context channel. Generate has no inspection tools and
cannot discover a local CSV schema from a filename alone.

The single-pass surface results before the W&B inline fix were:

| Surface | Model | Passed | Mean duration | Mean input | Mean output |
|---|---|---:|---:|---:|---:|
| Generate | DeepSeek | 3/3 | 18.6s | 1,002 | 3,085 |
| Generate | Qwen | 2/3 | 5.2s | 995 | 494 |
| Inline | DeepSeek | 3/3 | 5.1s | unavailable | unavailable |
| Inline | Qwen | 1/3 | 6.3s | unavailable | unavailable |

Qwen's long Generate failure was substantive. It emitted Polars code that
called a nonexistent `DataFrame.first()` method; it also represented
`activated_accounts` as a list instead of the requested count. The executable
grader rejected the result without relying on source style.

Qwen's inline failures initially looked like model-route incompatibility with
the endpoint's fixed 1,024-token budget. The medium and long cases consumed the
budget before emitting any text. In a repeated two-model short-case run,
DeepSeek passed 2/2 at a 5.9-second mean while Qwen failed 0/2 at an 8.4-second
mean for the same reason. Qwen had passed that short case once earlier.

Temporarily doubling the inline budget to 2,048 tokens did not help: Qwen
failed 0/3, consumed the larger budget before producing text each time, and
mean failure latency increased to 13.3 seconds. The production constant was
restored to 1,024.

The actual issue was provider translation. Inline completion already passed
the unified `thinking=False` setting, but W&B's OpenAI-compatible chat route
requires `extra_body.chat_template_kwargs.enable_thinking=false` for Qwen's
chat template. Added that request field only for W&B completion calls whose
caller explicitly disables thinking. Normal chat, structured Generate calls,
and other providers are unchanged.

With the template switch, Qwen passed 3/3 at a 3.3-second mean. A subsequent
three-repetition matrix passed 9/9 at a 3.0-second mean with a 0.12-second
population standard deviation. The 95% Wilson lower bound improved from 0 for
the failed two-trial observation to 0.70 over nine successes. This is both more
reliable and faster than increasing the token budget.

Logfire contained 19 traces across the six final comparison and token-budget
runs. Every trace had exactly one root span, and no span had a missing parent.
Failed inline requests retained their trace IDs in local artifacts after the
benchmark HTTP diagnostic change.

The 12 post-fix Qwen traces also each had exactly one root span and no missing
parent.

Conclusion: stop changing the seven-tool code-mode strategy for now. The next
evaluation work should add independently authored surface holdouts and run
repeated cross-model matrices. The first surface data already shows why the
three products need separate strategies: code-mode benefits from tools and
state inspection, Generate needs explicit context, and inline completion is
dominated by low-latency provider configuration and model compatibility.

## Experiment 30: Pydantic AI Harness capabilities

Date: 2026-09-30

Model: `deepseek-ai/DeepSeek-V4.1-Flash`

Runs: Code Mode smoke `20260930T083823Z-aeecae80`; initial long comparison
`20260930T083937Z-70e73cb2`; paired confirmation
`20260930T085601Z-0d0c314c`

Tested two hypotheses from `pydantic-ai-harness` 0.34.0 against the optimized
seven-tool hybrid:

- `ClearToolResults` as a generic replacement for marimo's semantic history
  compactor. It triggered at an estimated 20,000 tokens, retained eight recent
  tool pairs, cleared old tool inputs, and exempted exploratory
  `execute_code` results and capability loads.
- `CodeMode` around the six typed editor tools. Exploratory `execute_code`
  remained native because it executes Python in the live notebook kernel;
  Harness `run_code` executed orchestration in Monty with a 20-call nested
  tool budget.

The Code Mode smoke passed the short inventory task, proving that Monty could
marshal marimo's structured tool results. It took 57.5 seconds, seven visible
tools, six model requests, and 45,404 input tokens. The two long Code Mode
trials also passed, but both were materially less efficient than the current
hybrid:

| Two long cases | Current hybrid | Harness Code Mode | Change |
|---|---:|---:|---:|
| Passed | 2/2 | 2/2 | Equal |
| Mean duration | 369.6s | 470.3s | +27.2% |
| Mean tools | 36.0 | 48.0 | +33.3% |
| Mean tool errors | 2.5 | 5.0 | +100.0% |
| Mean model requests | 42.0 | 54.0 | +28.6% |
| Mean input tokens | 1,561,789 | 2,536,297 | +62.4% |
| Mean output tokens | 60,560 | 80,776 | +33.4% |

The model used `run_code`, but it did not consolidate notebook work. Across
the two long trials Logfire recorded 37 `run_code` calls, 57 native
`execute_code` calls, 23 nested inspections, and 14 nested patches. The extra
sandbox layer introduced another planning representation while the workflow
still required model decisions after notebook execution. This workload lacks
the large independent fan-out where programmatic tool calling is strongest.

Generic clearing was close in the initial comparison, so it was repeated.
Across two observations of both long scenarios, both strategies passed 4/4:

| Four long trials | Current hybrid | Harness clearing | Change |
|---|---:|---:|---:|
| Mean duration | 313.0s | 382.2s | +22.1% |
| Mean tools | 31.75 | 35.50 | +11.8% |
| Mean tool errors | 2.00 | 0.75 | -62.5% |
| Mean model requests | 37.50 | 40.00 | +6.7% |
| Mean input tokens | 1,261,768 | 1,476,791 | +17.0% |
| Mean output tokens | 51,219 | 64,487 | +25.9% |
| Mean reasoning tokens | 36,089 | 45,202 | +25.3% |

Logfire recorded 34 `compact_messages` spans for the generic variant, so the
result is not an inactive-threshold artifact. Generic clearing reduced errors
but retained recent redundant snapshots and patch bodies based only on pair
recency. Marimo's compactor understands that old notebook inspections and
successful patch source are superseded by live notebook state, and removes
them before Pydantic AI begins the next request. That domain knowledge was
more useful than a generic token threshold on these conversations.

`ToolOutputLimits` was not run as a third variant. Its default lossless spill
uses a process-local store, while marimo creates a new agent and capability
instance for every sidebar HTTP request. A handle emitted in one user turn
would not have a reader in a later turn without a conversation-scoped durable
store. Lossy truncation would discard notebook source that the semantic
compactor already handles more safely.

Trace verification across both long runs found 65 complete turn traces and
1,059 spans. Every trace had exactly one root and no child span had a missing
parent. Nested `run_code` calls remained visible as ordinary tool spans, so
observability was not the reason to reject Code Mode. [Open the initial
comparison in Logfire](https://logfire-us.pydantic.dev/shahmir/marimo-ai/?q=attributes-%3E%3E%27marimo.ai.eval.run_id%27+%3D+%2720260930T083937Z-70e73cb2%27&since=2026-09-30T08%3A35%3A00Z&until=2026-09-30T08%3A58%3A00Z)
and [the confirmation
run](https://logfire-us.pydantic.dev/shahmir/marimo-ai/?q=attributes-%3E%3E%27marimo.ai.eval.run_id%27+%3D+%2720260930T085601Z-0d0c314c%27&since=2026-09-30T08%3A55%3A00Z&until=2026-09-30T09%3A05%3A00Z).

Conclusion: retain the optimized seven-tool hybrid and its semantic history
compactor. Do not add Harness Code Mode, generic clearing, or a Harness runtime
dependency to the chat sidebar based on this evidence. Harness remains useful
as a design reference, especially for tool lifecycle hooks and traceable
nested calls, but its generic capabilities did not outperform marimo's
notebook-aware architecture. The rejected executable variants and dependency
were removed after recording the results.

## Experiment 31: incremental checkpoints for extreme conversations

Date: 2026-09-30

Model: `deepseek-ai/DeepSeek-V4.1-Flash`

Runs: initial 80,000-character workspace comparison
`20260930T101843Z-99a9a2f5`; repaired checkpoint transport
`20260930T102448Z-412045b8`; below-threshold recall comparison
`20260930T103127Z-43fb7d68`; forced recall comparison
`20260930T103540Z-eeb3fc63`; final hysteresis trials
`20260930T103946Z-197d52af`

Tested whether one sidebar thread can remain useful across many unrelated
tasks without summarizing the entire conversation on every request. Added two
holdouts:

- `multi_task_marathon` performs twelve turns across order, return, support,
  campaign, presentation, configuration, explanation, and audit tasks. It
  must retain three policies stated only in the first turn.
- `recall_marathon` performs ten turns across metric rewrites and an unrelated
  regional analysis, then restores two first-turn cells byte-for-byte.

All variants used the same seven editor tools. `hybrid_uncompacted` retained
the complete transcript, `hybrid_balanced` used the existing semantic tool
compactor, and `hybrid_checkpoint` added a benchmark-only incremental
checkpoint. The final checkpoint policy used a 60,000-character high-water
mark, kept the most recent five messages verbatim, and required at least two
newly completed turns between checkpoints. The complete transcript remained
in the runner; only the model-facing view changed.

The final checkpoint trials both passed:

| Scenario | Duration | Tools / errors | Requests | Input tokens | Checkpoints | Summary time | Final effective history |
|---|---:|---:|---:|---:|---:|---:|---:|
| Multi-task marathon | 341.4s | 38 / 1 | 52 | 977,885 | 3 | 21.1s | 82,918 chars |
| Recall marathon | 132.0s | 22 / 0 | 33 | 333,477 | 1 | 5.4s | 20,675 chars |

The recall checkpoint happened on turn eight, before the final exact restore.
The model still restored the original bounded metric and deleted audit cell
byte-for-byte through bounded revision history. This supports the intended
separation: summaries preserve semantic task context, while revision storage
preserves exact source.

Against the contemporaneous forced-recall comparison, checkpointing reduced
input tokens by 15.1% versus semantic compaction and 21.4% versus retaining
everything, while preserving correctness. The final hysteresis repeat had a
cheaper trajectory still: 333,477 input tokens and 132.0 seconds. On the
multi-task case, checkpointing reduced input by 33.2% versus the semantic
observation but used 14.7% more than the unusually cheap uncompacted
trajectory. It was also slower than both controls. This is high agent
trajectory variance, not evidence that a smaller context always makes an
individual run faster.

Across the two final checkpoint trials, summarization ran four times in 22
turns and added 26.5 seconds. It did not run on every request. Reusing a
watermark avoided re-summarizing old turns, and the two-turn hysteresis
prevented adjacent checkpoints. The first direct `urllib` W&B request was
rejected with HTTP 403; using the same OpenAI-compatible client stack as
marimo fixed the benchmark transport.

Conclusions:

- Keep the two extreme-conversation cases and history metrics.
- Keep incremental checkpoints as a benchmark experiment, not a production
  change yet. They bound model-facing history and preserved early semantic
  requirements and exact revision recovery, but latency and token gains are
  not consistent enough from this sample.
- Any production design should persist a checkpoint plus a watermark, retain
  the UI transcript separately, use hysteresis, and retrieve exact source
  from revision history rather than a summary.
- Repeat the comparison across another model and more repetitions before
  choosing a threshold or conversation-state storage architecture.

## Experiment 32: Pydantic AI history processing and persistent compaction

Date: 2026-09-30

Model: `deepseek-ai/DeepSeek-V4.1-Flash`

Runs: initial request-local comparison
`20260930T105556Z-531bdc59`; corrected ProcessHistory and semantic-summary
comparison `20260930T110116Z-04699e1b`; corrected request-local summary
comparison `20260930T110712Z-2a5d0161`; persistent Harness checkpoint
`20260930T111927Z-23bb8aa3`

Tested the history APIs in Pydantic AI 2.46.0 and
`pydantic-ai-harness` 0.34.0 against the two extreme-conversation holdouts.
The strategies were:

- `ProcessHistory` wrapping a 15,000-token sliding window.
- Request-local `SummarizingCompaction` with an 8,000-token retained tail.
- Marimo semantic tool trimming followed by the same summary.
- `TieredCompaction`, clearing old tool pairs before summarizing.
- Harness `compact_now` at a turn boundary, with the compacted history and a
  source-history watermark persisted across subsequent sidebar requests.

The summary model was explicitly run without thinking and allowed 4,096
output tokens. An initial 1,600-token limit failed during the multi-task case
because the nested summary exhausted its output budget before returning any
text. Provider-native `Model.compact_messages()` was not tested because the
W&B OpenAI chat transport does not implement it.

All corrected variants passed the delayed-recall case, but their costs were
materially different:

| Recall strategy | Duration | Tools / errors | Requests | Input tokens |
|---|---:|---:|---:|---:|
| Persistent custom checkpoint | 132.0s | 22 / 0 | 33 | 333,477 |
| ProcessHistory sliding window | 133.4s | 38 / 1 | 47 | 466,768 |
| Request-local summary | 248.7s | 29 / 1 | 44 | 411,819 |
| Semantic + request-local summary | 160.3s | 25 / 0 | 44 | 350,932 |
| Request-local tiered summary | 176.5s | 26 / 0 | 42 | 396,685 |
| Persistent Harness checkpoint | 97.7s | 24 / 0 | 34 | 444,749 |

`ProcessHistory` did not solve the sidebar lifecycle problem. Marimo creates a
new Pydantic AI agent for each HTTP request and the browser sends the complete
UI transcript again. A capability can compact the repeated model requests in
one tool loop, but its transformed history is not the next user turn's input.
The sliding window also removed useful causal context and caused substantially
more notebook re-inspection and tool use.

Request-local summaries have the same lifecycle mismatch. Logfire recorded
18 `compact_messages` spans and 18 summary-agent invocations for the 12-turn
multi-task trial, plus eight of each for the 10-turn recall trial. Thus 22 user
turns generated 26 summaries, sometimes more than once in one tool loop. Both
trials passed, but the multi-task trial used 55 tools and 81 model requests;
the recall trial took 248.7 seconds. Combining semantic trimming with generic
summarization and adding a clearing tier did not remove the repeated work.

The persistent Harness experiment used `compact_now` between agent runs and
round-tripped Pydantic model messages through `VercelAIAdapter`. Marimo retained
the complete UI transcript separately and persisted only the compacted
model-facing history plus a watermark. It summarized four times in 22 turns,
not on every request, and both trials passed:

| Scenario | Duration | Tools / errors | Requests | Input tokens | Checkpoints | Summary time | Final effective history |
|---|---:|---:|---:|---:|---:|---:|---:|
| Multi-task marathon | 274.6s | 38 / 1 | 49 | 879,632 | 3 | 13.3s | 45,273 chars |
| Recall marathon | 97.7s | 24 / 0 | 34 | 444,749 | 1 | 6.1s | 57,341 chars |

Compared with request-local Harness summarization, the persistent form reduced
model requests by 40% and tools by 31% on the multi-task trial, and reduced
latency by 61% on recall. Its multi-task input was 8% higher, so minimizing
tokens inside one run is not the same objective as minimizing repeated
conversation work.

Compared with the custom persistent checkpoint from Experiment 31, Harness
`compact_now` was 20% faster and used 10% fewer input tokens on multi-task,
with the same tool count. On recall it was 26% faster but used 33% more input
tokens and two more tools. With one observation per trajectory, this does not
establish that either summarizer is uniformly better. It does establish that
persistence across turns is the important architectural choice.

A second-model comparison used `Qwen/Qwen3.5-35B-A3B`. At the normal
60,000-character threshold, neither recall variant compacted: Qwen's shorter
responses kept the effective history below the threshold. The initial
multi-task attempts were also not useful architecture comparisons. Both
variants repeatedly exhausted the single retry for `apply_notebook_patch`
before compaction activated. One Harness trial completed, but still generated
no checkpoint.

The comparison was therefore repeated on the more stable recall scenario with
an explicit 25,000-character threshold. This found and corrected two benchmark
problems:

- The custom checkpoint summarizer had not disabled Qwen's thinking template,
  and once consumed its output budget without returning visible text. It now
  uses the same 4,096-token non-thinking settings as the Harness summarizer.
- Harness's fixed 8,000-token retained tail could exceed the entire
  conversation even after the character threshold fired. The wrapper now
  scales the retained tail with the threshold and does not count or persist a
  no-op compaction.

After those corrections, three independent forced-threshold recall trials per
strategy produced:

| Qwen recall, three trials | Custom checkpoint | Harness `compact_now` |
|---|---:|---:|
| Passed | 3/3 | 2/3 |
| Mean duration | 62.9s | 80.5s |
| Mean tools | 26.0 | 32.0 |
| Mean tool errors | 2.3 | 4.7 |
| Mean model requests | 37.0 | 44.0 |
| Mean input tokens | 220,082 | 282,265 |
| Mean output tokens | 7,981 | 10,649 |
| Mean checkpoints | 1.3 | 3.0 |

Runs: inactive-threshold and unstable multi-task comparison
`20260930T124810Z-17fa22ea`; multi-task rerun
`20260930T124935Z-76bdc293`; custom summary failure before the thinking fix
`20260930T125057Z-74780552`; corrected no-op probe
`20260930T125359Z-e20e6fb1`; corrected forced comparison
`20260930T125545Z-65ac34b9`; two-repetition confirmation
`20260930T125743Z-3e2e2778`.

The failed Harness trial produced correct values but did not restore the two
first-turn cells byte-for-byte. The model claimed exact restoration after
inspection and revision-history use, but the executable source contract found
formatting or source differences. More frequent generic summaries did not
improve recall and instead increased requests and exploration.

Conclusion: use a conversation-scoped history manager as the production
boundary. It should retain the immutable UI transcript, maintain a separate
model-facing checkpoint and source-history watermark, compact only after a
high-water mark with hysteresis, and execute compaction under the triggering
turn's trace. Harness `compact_now` is a good implementation candidate because
it operates explicitly between agent runs, but the cross-model results do not
justify its runtime dependency or generic summary policy. The custom
notebook-aware checkpoint is the better current prototype. Replace its fixed
character trigger with a model-context or estimated-token budget before a
production experiment. `ProcessHistory` remains useful as an intra-run
emergency limit, not as the primary long-conversation mechanism. Do not add
request-local summarization, tiered clearing, or Harness compaction to the
production sidebar based on these results.
