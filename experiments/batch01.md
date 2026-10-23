# Batch 01, candidate 1: Hoist the quiet-move pawn-history bucket

Branch: `bench/b01-01-pawn-history-hoist`

Base: `effdc3fd3f6de6e75fe1374a51a7a7eed66f880b` (the same parent for every batch-01 candidate).

## Hypothesis

Resolve the invariant pawn-history bucket once per quiet move list, instead of repeating its key/mask/address lookup for each move. Atomic history entries are still read for every move. Compiler optimization may already remove some of this work; measurement is required.

Scope: Portable quiet-move scoring.

This is an experimental non-functional candidate. No speed gain or Elo gain has been measured or claimed. Benchmark it independently against the pinned base, using identical compiler, target and PGO settings.

## Correctness

Compiled locally with GCC 13.3.0 for `x86-64-avx512icl` and `x86-64-avx2`, using release builds with LTO (without PGO). Both targets exactly match their corresponding baseline's normalized score/PV/bestmove traces and total nodes at depths 13 and 14 over Stockfish's default bench positions. Only the time and NPS fields were removed from compared trace lines.

- Default depth-13 signature: **1559611**.
- Default depth-14 signature: **3178836**.
- One thread and 16 MiB hash for equivalence checks.
- `git diff --check` passed.
- Other compiler/architecture builds, debug/sanitizer checks and randomized-position equivalence tests were not run in this batch.
- Multithreaded and time-limited searches are not expected to have identical traces because of scheduling and shared search state.

Full per-target results are in `experiments/batch01-candidate.json`.

## VM test contract

Use only the three explicitly listed branches for batch 01:

```
bench/b01-01-pawn-history-hoist
bench/b01-02-threat-lut16
bench/b01-03-next-tile-prefetch
```

Baseline ref: `bench/b01-base`, pinned to `effdc3fd3f6de6e75fe1374a51a7a7eed66f880b`. None of the candidate branches includes another candidate's source changes.

For each candidate, record the resolved commit SHA, build it with the same options as baseline, and check the default bench signature before timing. Clean objects when switching candidates or architecture to prevent reusing an executable/object built with different flags. A suitable performance build on the user's AVX-512 VM is:

```sh
make -C src -j profile-build ARCH=x86-64-avx512icl
```

Run paired, warmed comparisons on fixed CPU sets. If testing four threads on a four-vCPU VM, run engines sequentially. Preserve raw results and uncertainty, and test promising results again before calling a gain. Keep one shared network file/build checkout where possible to limit disk use.

Reproduce the local correctness check with:

```sh
src/stockfish bench
src/stockfish bench 16 1 14
```

Both engines must have matching complete fixed-depth search traces, in addition to matching aggregate node totals. A matching signature alone is a useful guard, but is not a complete proof for every possible position.
