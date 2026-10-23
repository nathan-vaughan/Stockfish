# Batch 02, candidate 8: Use scalar insertion sort for up to four moves

Branch: `bench/b02-08-small-move-sort`.
Base: `effdc3fd3f6de6e75fe1374a51a7a7eed66f880b` (`bench/b01-base`).

## Hypothesis

Use the existing stable scalar insertion loop when a move list has at most four elements, avoiding AVX-512 sorter initialization, expansion and output interleaving. Larger lists keep the existing vector sorter. The threshold branch is an extra cost.

Scope: AVX-512 partial insertion sorting.

This candidate starts directly from the pinned base. It does not include another batch-01 or batch-02 candidate's source changes. It is an experiment for VM measurement: no performance benefit or Elo gain has been established or claimed.

## Validation

GCC 13.3.0 release builds with LTO (without PGO), on AMD EPYC 9V74:

- Compiled for `x86-64-avx512icl` and `x86-64-avx2`.
- Both targets matched their respective baseline's complete normalized score/PV/bestmove traces and node totals on the default bench at depths 13 and 14.
- Default depth-13 bench: **1559611**; depth 14: **3178836**.
- Both targets matched traces and totals on **67** deterministic random-game and special-case positions at depth 8.
- Both targets matched perft totals for seven special positions at depth 3, covering castling, en passant, promotions, pins and checks.
- Trace comparisons removed only time and NPS fields. One thread and 16 MiB hash.
- `git diff --check` passed.
- Additional comparison against the original move sorter passed 16640 cases over list lengths 0..64, including ties and varying partial-sort limits. The entire active output order was compared.

Other compilers, other instruction-set targets, PGO, debug/sanitizer builds and timing/multithreaded equivalence were not tested locally in this batch. Time-limited and multithreaded searches naturally vary with scheduling and available search time.

Full validation details are in `experiments/batch02-candidate.json`. Reproduce the stored equivalence cases from the repository root:

```sh
python3 experiments/batch02/check_equivalence.py /path/to/base /path/to/candidate
```

## VM measurement

Build baseline and each candidate with identical compiler and target flags. Clean objects when changing source/architecture. For the user's AVX-512 VM:

```sh
make -C src -j profile-build ARCH=x86-64-avx512icl
src/stockfish bench
```

Expected default bench is `1559611`. Record the exact candidate commit SHA and raw paired results. Warm both engines, alternate run order, and use fixed CPU sets. Run four-thread engines sequentially on a four-vCPU VM. Use one shared network/check-out where practical to conserve disk space. Do not stack these candidates for initial testing; combinations are separate experiments.

Explicit batch-02 branch list:

```
bench/b02-01-accumulator-tile8
bench/b02-02-nnz32-compaction
bench/b02-03-vnni-two-chains
bench/b02-04-threat-prefetch-t0
bench/b02-05-small-splat
bench/b02-06-see-slider-hoist
bench/b02-07-direct-psq-indices
bench/b02-08-small-move-sort
bench/b02-09-aligned-nnz-buffer
```
