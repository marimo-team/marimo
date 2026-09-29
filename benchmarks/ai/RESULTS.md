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
