# Batch 03: 24 independent non-functional speed experiments

Every candidate is based directly on master `effdc3fd3f6de6e75fe1374a51a7a7eed66f880b`.
None includes another candidate, the original 12 source changes, or the combined `latest` branch.
Performance is unmeasured. These changes trade instruction count, code size, register pressure,
memory traffic or branch behavior; regressions are expected for some candidates.

| Branch | Idea |
|---|---|
| `bench/b03-01-tt-probe-unroll` | Unroll the three TT key probes |
| `bench/b03-02-tt-replacement-score` | Carry the current TT replacement score |
| `bench/b03-03-tt-write-prefetch` | Prefetch child TT clusters for writing |
| `bench/b03-04-no-contcorr-prefetch` | Remove continuation-correction prefetches |
| `bench/b03-05-history-unsigned-decay` | Compute history decay with an unsigned quotient |
| `bench/b03-06-continuation-unroll` | Specialize the five continuation-history updates |
| `bench/b03-07-leaper-before-hq` | Return leaper attacks before computing HQ |
| `bench/b03-08-hq-bishop-extract` | Combine bishop HQ lanes with 128-bit operations |
| `bench/b03-09-hq-inline-rank-lut` | Embed rank attack bytes beside HQ masks |
| `bench/b03-10-repetition-unroll` | Inspect two repetition states per loop |
| `bench/b03-11-legal-pawn-lazy` | Short-circuit pawn legality alternatives |
| `bench/b03-12-blockers-popcount` | Use POPCNT for singleton slider blockers |
| `bench/b03-13-movegen-occupancy` | Cache occupancy for each piece-generation pass |
| `bench/b03-14-pawn-encoded-splat` | Construct pawn moves in encoded-square space |
| `bench/b03-15-capture-mvv-table` | Precompute scaled MVV capture values |
| `bench/b03-16-fc2-wide-dot` | Use AVX-512 VNNI for the final scalar layer |
| `bench/b03-17-activation-ymm` | Use YMM paired activations on AVX-512 |
| `bench/b03-18-activation-mask-shift` | Mask negative activations during the shift |
| `bench/b03-19-network-scalar-output` | Use scalar storage for the final network result |
| `bench/b03-20-dense-noalias` | Declare dense-layer input and output nonaliasing |
| `bench/b03-21-changed-board-zmm` | Compare cached piece boards in one ZMM operation |
| `bench/b03-22-pawn-pair-fast-exit` | Skip both-perspective pawn-pair dispatch when unchanged |
| `bench/b03-23-accumulator-ready-exit` | Return immediately when both latest accumulators are ready |
| `bench/b03-24-material-zero-correlation` | Skip normalization divisions at equal material |

## Validation

Each published candidate passed a GCC 13.3 release/LTO build without PGO on AMD EPYC 9V74,
target `x86-64-avx512icl`, and matched a fresh master build's normalized score/PV/bestmove
traces and aggregate node totals (one thread, 16 MiB hash):

- Default bench depth 13: 1559611 nodes.
- Default bench depth 14: 3178836 nodes.
- 67 stored random-game/special positions at depth 8: 82787 nodes.
- Seven special positions at perft depth 3: 187239 nodes.
- Whitespace checked with `git diff --check`.

These checks are not exhaustive proofs. Other compilers/targets, PGO, sanitizers and
multithread timing were not validated locally in this batch. Normal concurrent TT/history
races and time-limited searches can vary. Candidate 02 caches replacement-score snapshots
inside an already racy shared TT; it preserves the single-thread replacement policy.

Reproduce the stored checks:

```bash
python3 experiments/batch03/check_equivalence.py /path/to/master /path/to/candidate
```

## VM batch command

The existing `stockfish_batch.py` discovers this batch automatically. To test only the 24
new branches, use a separate work directory and explicit branch selection:

```bash
args=()
while read -r sha ref; do
  args+=(--branch "${ref#refs/heads/}")
done < <(git ls-remote --heads https://github.com/nathan-vaughan/Stockfish.git 'refs/heads/bench/b03-*')

if [ "${#args[@]}" -eq 48 ]; then
  nohup python3 -u ~/stockfish_batch.py --workdir ~/stockfish-batch03 \
    --runs 100 "${args[@]}" > ~/stockfish-batch03.log 2>&1 &
  tail -f ~/stockfish-batch03.log
else
  echo "Expected exactly 24 batch-03 branches; not starting."
fi
```

CSV summary: `~/stockfish-batch03/summary.csv`. Preserve raw results and source hashes.
The runner uses one checkout/network cache, master executable and current candidate to
limit disk space. Retest promising source changes with independent builds and unchanged-master
controls: confidence intervals within a run do not account for build/runtime bias.
Do not assume individual gains will add when combining candidates.
