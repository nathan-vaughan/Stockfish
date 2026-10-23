# Stockfish branch speed tests

Linux, Python 3.9+, git, GNU make, g++, and wget or curl are required. The default target is `x86-64-avx512icl`, intended for the EPYC 9B45 VM. Run no other CPU-heavy tasks while measuring.

```bash
wget -O ~/stockfish_batch.py https://raw.githubusercontent.com/nathan-vaughan/Stockfish/tools/branch-speedtest/tools/bench_branches.py
nohup python3 -u ~/stockfish_batch.py --runs 100 > ~/stockfish-batch.log 2>&1 &
tail -f ~/stockfish-batch.log
```

Ctrl+C exits `tail`; the background test continues. To stop the runner, send SIGINT to its Python process. Re-running the identical Python command resumes complete saved pairs; do not start two runners together.

The runner fetches the fork and discovers all `bench/bNN-NN-*` experiment branches (currently 12). It excludes the baseline alias, tools branches, and unrelated functional experiments. Every candidate must be marked ready in its metadata and reference the current master commit. If master has advanced, it stops rather than measuring candidates against a different baseline.

Master and candidates use the same GCC PGO build command, with four parallel build jobs at most by default. The script maintains one checkout, shared NNUE files, one saved master executable, and the current candidate executable. It does not retain twelve separate builds. Builds require at least 1 GiB free at their start; actual requirements depend on the compiler. The VM's reported 3.8 GB free should be sufficient for this workflow, but the script does not remove unrelated files or install packages.

Each candidate's single-thread depth-13 bench node total must match master before timing. Timing uses depth 13, 16 MiB hash, one thread. Two warmup pairs are excluded. Each of the 100 measured pairs runs master once and the candidate once. On machines with two known physical cores, both engines run concurrently, pinned before exec to distinct physical cores, with CPU assignments swapped every pair. Otherwise tests run sequentially in alternating order. The topology check uses Linux sysfs, not assumptions about logical CPU numbering. With `--threads 4`, tests automatically run sequentially on the available CPU set to avoid running eight search threads on four vCPUs.

Results use the paired NPS-difference approach familiar from [pyshbench](https://github.com/hazzl/pyshbench), implemented with the Python standard library. The summary includes arithmetic speedup, a paired geometric speedup and approximate normal 95% interval, and a normal-CDF statistic for positive mean NPS difference. This statistic is not a posterior probability or a multiple-testing correction. Retest apparent winners in a fresh independent measurement before treating them as gains. VM contention, frequency changes, and simultaneous engine activity can affect results.

Files:

- `~/stockfish-bench/summary.csv`: successful candidates from the latest run, updated after each candidate.
- `~/stockfish-bench/runs/<configuration-id>/config.json`: frozen source commits, compiler, CPU sets, settings, and runner hash.
- Same directory: append-only raw pair JSONL files, build logs, and `failures.json`.
- Build or signature failures are logged; the runner continues with the next candidate and exits unsuccessfully if any failed.

Every complete pair is flushed to disk. Resume reuses results only for an identical source/configuration snapshot; changing architecture, depth, CPU settings, source commits, or runner version creates a separate result directory. Increasing `--runs` extends the saved measurements. Completed candidates do not rebuild. Fresh source snapshots preserve older result directories. Do not combine measurements taken on different hardware or under substantially different VM conditions.

Options:

```bash
# One candidate only (exact remote branch name):
python3 -u ~/stockfish_batch.py --branch bench/b02-02-nnz32-compaction --runs 100

# A separate AVX2 experiment:
python3 -u ~/stockfish_batch.py --arch x86-64-avx2 --runs 100

# Alternate sequential runs, or multi-thread tests:
python3 -u ~/stockfish_batch.py --sequential --runs 100
python3 -u ~/stockfish_batch.py --threads 4 --runs 100
```

Additional options: `--workdir`, `--repo`, `--depth`, `--jobs`. Branch selections can repeat `--branch`. Bench node equality at timed depth is required for single-thread runs; multi-thread search can legitimately have different node totals, so only its separate single-thread validation is enforced.

Local runner validation:

```bash
python3 tools/test_bench_branches.py
```

Tests exercise statistics, recovery from a partial append, and clone/build/discovery/resume against a miniature local Git fixture. The benchmark launcher was also smoke-tested with actual master and candidate AVX-512 binaries in both concurrent and sequential modes. This validates the runner, not any speedup claim.
