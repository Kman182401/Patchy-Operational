# Delegation And Review

Use a strong primary agent first. Add subagents only when they materially improve correctness, coverage, or throughput.

## Good Reasons To Delegate
- independent research branches
- bounded code changes with disjoint ownership
- large test-output or log analysis
- targeted code review or adversarial verification

## Bad Reasons To Delegate
- to look sophisticated
- to duplicate the main thread's work
- to offload the next blocking step when doing it directly would be faster

## Delegation Rules
1. Give each subagent a narrow charter.
2. Define ownership clearly for write tasks.
3. Avoid overlapping edits.
4. Do not wait repeatedly by reflex.
5. Review subagent output before integrating it.
6. If a delegated result changes the plan contract, update the plan explicitly.
