# Batch 04: 24 independent non-functional speed experiments

Every candidate is based directly on master `effdc3fd3f6de6e75fe1374a51a7a7eed66f880b`.
None includes another candidate, the previous 36 ideas, or the combined `latest` branch.
Performance is unmeasured. These changes trade instruction count, code size, register pressure,
memory traffic or branch behavior; regressions are expected for some candidates.

| Branch | Idea |
|---|---|
| `bench/b04-01-scalar-hyperbola` | Replace vector dual-HQ with scalar byte-swap HQ |
| `bench/b04-02-hq-vbmi-permute` | Use VBMI byte permutations in HQ |
| `bench/b04-03-rank-pext` | Extract HQ rank occupancy with PEXT |
| `bench/b04-04-state-cacheline` | Align position state records to cache lines |
| `bench/b04-05-stack-hot-fields` | Place current search moves beside continuation pointers |
| `bench/b04-06-list-count32` | Use 32-bit lengths in bounded feature lists |
| `bench/b04-07-finny-header-first` | Place Finny metadata before cached neurons |
| `bench/b04-08-computed-header` | Place accumulator validity flags before neuron arrays |
| `bench/b04-09-delta-before-source` | Accumulate feature deltas before loading source neurons |
| `bench/b04-10-empty-delta-copy` | Copy unchanged accumulator perspectives directly |
| `bench/b04-11-tt-probe-outline` | Keep TT probing outside the recursive search body |
| `bench/b04-12-direct-ep-legality` | Validate en passant TT moves directly |
| `bench/b04-13-quiet-threat-table` | Score escape/destination threat status with a four-entry table |
| `bench/b04-14-dense-first-layer` | Sweep the first NNUE layer densely |
| `bench/b04-15-threat-rank-popcount` | Replace the large threat destination LUT with POPCNT |
| `bench/b04-16-final-hadd` | Use horizontal-add instructions for scalar output reduction |
| `bench/b04-17-split-activations` | Run independent squared and linear activation kernels |
| `bench/b04-18-dense-output-major` | Process dense NNUE output blocks outermost |
| `bench/b04-19-word-move-compaction` | Compact preencoded 16-bit destination moves |
| `bench/b04-20-slider-target-reject` | Reject unreachable slider target sets before HQ |
| `bench/b04-21-tt-save-key-snapshot` | Load the existing TT key once during save |
| `bench/b04-22-cuckoo-parallel-load` | Load both upcoming-repetition cuckoo slots eagerly |
| `bench/b04-23-reciprocal-normalization` | Normalize evaluation with corrected reciprocal estimates |
| `bench/b04-24-finny-clean-store` | Avoid writing unchanged Finny neuron rows |

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
races and time-limited searches can vary. Candidate 21 reuses a key snapshot inside an already racy shared TT; it preserves the single-thread policy.

Reproduce the stored checks:

```bash
python3 experiments/batch04/check_equivalence.py /path/to/master /path/to/candidate
```

## VM batch command

The existing `stockfish_batch.py` discovers this batch automatically. To test only the 24
new branches, use a separate work directory and explicit branch selection:

```bash
args=()
while read -r sha ref; do
  args+=(--branch "${ref#refs/heads/}")
done < <(git ls-remote --heads https://github.com/nathan-vaughan/Stockfish.git 'refs/heads/bench/b04-*')

if [ "${#args[@]}" -eq 48 ]; then
  nohup python3 -u ~/stockfish_batch.py --workdir ~/stockfish-batch04 \
    --runs 100 "${args[@]}" > ~/stockfish-batch04.log 2>&1 &
  tail -f ~/stockfish-batch04.log
else
  echo "Expected exactly 24 batch-04 branches; not starting."
fi
```

CSV summary: `~/stockfish-batch04/summary.csv`. Preserve raw results and source hashes.
The runner uses one checkout/network cache, master executable and current candidate to
limit disk space. Retest promising source changes with independent builds and unchanged-master
controls: confidence intervals within a run do not account for build/runtime bias.
Do not assume individual gains will add when combining candidates.
