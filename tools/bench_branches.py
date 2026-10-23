#!/usr/bin/env python3
"""Linux, Python 3.9+: bounded-storage, resumable Stockfish branch speed tests."""
import argparse
import csv
import fcntl
import hashlib
import io
import json
import math
import os
from pathlib import Path
import platform
import re
import shutil
import signal
import statistics as st
import subprocess as sp
import tempfile

VERSION = 1


def command(args, cwd=None):
    return sp.check_output(args, cwd=cwd, text=True, stderr=sp.STDOUT).strip()


def atomic(path, value):
    path = Path(path)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(value)
    temp.replace(path)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()[:16]


def file_hash(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def cpu_sets():
    allowed = sorted(os.sched_getaffinity(0))
    cores = {}
    for cpu in allowed:
        root = Path('/sys/devices/system/cpu') / ('cpu%d' % cpu) / 'topology'
        try:
            key = (root.joinpath('physical_package_id').read_text().strip(),
                   root.joinpath('core_id').read_text().strip())
        except OSError:
            # Unknown topology: sequential tests avoid accidentally pairing siblings.
            return [allowed]
        cores.setdefault(key, []).append(cpu)
    return [[v[0]] for v in cores.values()]


def parse_bench(text):
    nodes = re.search(r'Nodes searched\s*:\s*(\d+)', text)
    nps = re.search(r'Nodes/second\s*:\s*(\d+)', text)
    if not nodes or not nps or int(nps[1]) <= 0:
        raise RuntimeError('Missing or invalid benchmark output: ' + text[-1200:])
    return {'nodes': int(nodes[1]), 'nps': int(nps[1])}


def run_engines(jobs, threads, depth, concurrent):
    """Affinity is installed in each child before exec; no timing of startup."""
    children = []
    outputs = []
    def launch(binary, cpus):
        output = tempfile.TemporaryFile(mode='w+t')
        outputs.append(output)
        proc = sp.Popen([str(binary), 'bench', '16', str(threads), str(depth)],
                        stdout=sp.DEVNULL, stderr=output, start_new_session=True,
                        preexec_fn=lambda: os.sched_setaffinity(0, cpus))
        children.append(proc)
        return proc, output
    def finish(proc, output):
        proc.wait(timeout=600)
        output.seek(0)
        text = output.read()
        if proc.returncode:
            raise RuntimeError('Engine exited %d: %s' % (proc.returncode, text[-1200:]))
        return parse_bench(text)
    try:
        if concurrent:
            running = [launch(*job) for job in jobs]
            return [finish(*item) for item in running]
        return [finish(*launch(*job)) for job in jobs]
    finally:
        for proc in children:
            if proc.poll() is None:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait()
        for output in outputs:
            output.close()


def pair(base, test, sets, index, threads, depth, concurrent):
    if concurrent:
        cpus = sets if index % 2 == 0 else sets[::-1]
        values = run_engines([(base, cpus[0]), (test, cpus[1])], threads, depth, True)
    else:
        jobs = [(base, sets[0]), (test, sets[0])]
        if index % 2:
            jobs.reverse()
        values = run_engines(jobs, threads, depth, False)
        if index % 2:
            values.reverse()
    if threads == 1 and values[0]['nodes'] != values[1]['nodes']:
        raise RuntimeError('Node mismatch in timed pair: %s' % values)
    return {'pair': index, 'base': values[0], 'test': values[1]}


def summarize(pairs):
    base = [p['base']['nps'] for p in pairs]
    test = [p['test']['nps'] for p in pairs]
    delta = [t - b for b, t in zip(base, test)]
    logs = [math.log(t / b) for b, t in zip(base, test)]
    se = st.stdev(delta) / math.sqrt(len(delta)) if len(delta) > 1 else 0
    log_se = st.stdev(logs) / math.sqrt(len(logs)) if len(logs) > 1 else 0
    mean = st.mean(delta)
    probability = st.NormalDist().cdf(mean / se) if se else (1 if mean > 0 else 0 if mean < 0 else .5)
    return dict(runs=len(pairs), base_nps=st.mean(base), test_nps=st.mean(test),
                speedup_pct=100 * mean / st.mean(base), diff_nps=mean,
                diff_95=1.96 * se, p_positive_normal=probability,
                geometric_pct=100 * math.expm1(st.mean(logs)),
                geometric_low_95=100 * math.expm1(st.mean(logs) - 1.96 * log_se),
                geometric_high_95=100 * math.expm1(st.mean(logs) + 1.96 * log_se))


def load_pairs(path):
    if not path.exists():
        return []
    data = path.read_bytes()
    # A power loss may leave the last append incomplete. Keep complete lines only.
    complete = data[:data.rfind(b'\n') + 1]
    if complete != data:
        path.write_bytes(complete)
    pairs = [json.loads(line) for line in complete.splitlines()]
    for i, item in enumerate(pairs):
        if item['pair'] != i:
            raise RuntimeError('Invalid pair sequence in ' + str(path))
    return pairs


def build(repo, sha, args, log):
    if shutil.disk_usage(args.workdir).free < 1024 ** 3:
        raise RuntimeError('Less than 1 GiB free; free disk space before building.')
    command(['git', 'checkout', '--detach', '--force', sha], repo)
    with open(log, 'w') as f:
        proc = sp.Popen(['make', '-j%d' % args.jobs, 'profile-build',
                         'ARCH=' + args.arch, 'COMP=gcc', 'CXX=g++'],
                        cwd=repo / 'src', stdout=f, stderr=sp.STDOUT,
                        start_new_session=True)
        try:
            if proc.wait(timeout=3600):
                raise RuntimeError('Build failed; see ' + str(log))
        finally:
            if proc.poll() is None:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait()
    binary = repo / 'src/stockfish'
    if not binary.is_file():
        raise RuntimeError('Build produced no src/stockfish')
    return binary


def write_summary(work, run, rows):
    if not rows:
        return
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    atomic(run / 'summary.csv', out.getvalue())
    atomic(work / 'summary.csv', out.getvalue())


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', default='https://github.com/nathan-vaughan/Stockfish.git')
    parser.add_argument('--workdir', type=Path, default=Path.home() / 'stockfish-bench')
    parser.add_argument('--runs', type=int, default=100, help='paired runs per candidate (default 100)')
    parser.add_argument('--jobs', type=int, default=min(4, os.cpu_count() or 1))
    parser.add_argument('--arch', default='x86-64-avx512icl')
    parser.add_argument('--depth', type=int, default=13)
    parser.add_argument('--threads', type=int, default=1)
    parser.add_argument('--sequential', action='store_true')
    parser.add_argument('--branch', action='append', help='select one or more bench candidate branches')
    args = parser.parse_args(argv)
    if min(args.runs, args.jobs, args.depth, args.threads) < 1:
        parser.error('numeric arguments must be positive')
    for tool in ('git', 'make', 'g++'):
        if not shutil.which(tool):
            parser.error('Missing dependency: ' + tool)
    work = args.workdir.expanduser().resolve()
    args.workdir = work
    work.mkdir(parents=True, exist_ok=True)
    with open(work / 'runner.lock', 'w') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            parser.error('Another runner already uses ' + str(work))
        repo = work / 'repo'
        marker = work / 'managed-repo.json'
        if repo.exists():
            if not marker.exists() or json.loads(marker.read_text()) != {'repo': args.repo}:
                parser.error('Refusing to use an unrecognized existing checkout: ' + str(repo))
            if command(['git', 'remote', 'get-url', 'origin'], repo) != args.repo:
                parser.error('Checkout origin does not match --repo')
        else:
            print('Cloning ' + args.repo, flush=True)
            command(['git', 'clone', '--no-checkout', args.repo, str(repo)])
            atomic(marker, json.dumps({'repo': args.repo}))
        print('Fetching branch snapshot...', flush=True)
        command(['git', 'fetch', '--prune', 'origin', '+refs/heads/*:refs/remotes/origin/*'], repo)
        refs = command(['git', 'for-each-ref', '--format=%(refname:strip=3) %(objectname)',
                        'refs/remotes/origin'], repo)
        branches = dict(line.split() for line in refs.splitlines())
        master = branches['master']
        candidates = {b: sha for b, sha in branches.items()
                      if re.fullmatch(r'bench/b\d+-\d+-.+', b)}
        if args.branch:
            missing = set(args.branch) - candidates.keys()
            if missing:
                parser.error('Not benchmark candidate branches: ' + ', '.join(sorted(missing)))
            candidates = {b: candidates[b] for b in args.branch}
        if not candidates:
            parser.error('No bench/bNN-NN-* candidates found')
        # Prevent comparison of old candidate trees against a newer baseline.
        for branch, sha in candidates.items():
            metadata = command(['git', 'ls-tree', '-r', '--name-only', sha, 'experiments'], repo)
            paths = [p for p in metadata.splitlines() if re.fullmatch(r'experiments/batch\d+-candidate.json', p)]
            if len(paths) != 1:
                raise RuntimeError('Expected one candidate metadata file: ' + branch)
            info = json.loads(command(['git', 'show', sha + ':' + paths[0]], repo))
            if info.get('base_commit') != master or not info.get('ready_for_vm_benchmark'):
                raise RuntimeError(branch + ' is not marked ready against current master ' + master)
        physical = cpu_sets()
        concurrent = args.threads == 1 and len(physical) >= 2 and not args.sequential
        sets = physical[:2] if concurrent else [sorted(os.sched_getaffinity(0))]
        if args.threads > len(sets[0]) and not concurrent:
            parser.error('--threads exceeds allowed logical CPUs')
        config = dict(version=VERSION, repo=args.repo, master=master,
                      candidates=candidates, arch=args.arch, compiler=command(['g++', '--version']),
                      threads=args.threads, depth=args.depth, sets=sets, concurrent=concurrent,
                      hostname=platform.node(), cpuinfo=[line for line in Path('/proc/cpuinfo').read_text().splitlines()
                               if line.startswith(('vendor_id', 'model name', 'cpu family', 'model\t', 'stepping'))],
                      kernel=platform.release(), script_sha256=file_hash(Path(__file__)))
        run = work / 'runs' / digest(config)
        run.mkdir(parents=True, exist_ok=True)
        atomic(run / 'config.json', json.dumps(config, indent=2))
        print('Master: %s\nCandidates: %d; %d pairs each\nMode: %s; CPUs: %s\nResults: %s'
              % (master, len(candidates), args.runs, 'concurrent' if concurrent else 'sequential', sets, run), flush=True)
        base = work / 'master'
        cache = work / 'master-build.json'
        identity = dict(master=master, arch=args.arch, compiler=config['compiler'], version=VERSION)
        cached = json.loads(cache.read_text()) if cache.exists() else {}
        if not base.exists() or cached.get('identity') != identity or cached.get('sha256') != file_hash(base):
            print('Building master (PGO)...', flush=True)
            built = build(repo, master, args, run / 'master-build.log')
            shutil.copy2(built, work / 'master.tmp')
            (work / 'master.tmp').replace(base)
            atomic(cache, json.dumps(dict(identity=identity, sha256=file_hash(base))))
        signature = run_engines([(base, sets[0])], 1, 13, False)[0]['nodes']
        rows = []
        failures = []
        for branch, sha in sorted(candidates.items()):
            slug = branch.replace('/', '--') + '-' + sha[:8]
            path = run / (slug + '.jsonl')
            pairs = load_pairs(path)
            print('\n%s [%s], %d/%d saved' % (branch, sha[:8], len(pairs), args.runs), flush=True)
            try:
                if len(pairs) < args.runs:
                    print('Building candidate (PGO)...', flush=True)
                    test = build(repo, sha, args, run / (slug + '-build.log'))
                    check = run_engines([(test, sets[0])], 1, 13, False)[0]['nodes']
                    if check != signature:
                        raise RuntimeError('Default bench signature differs: master %d, test %d' % (signature, check))
                    print('Signature matched: %d. Warming up...' % signature, flush=True)
                    pair(base, test, sets, 0, args.threads, args.depth, concurrent)
                    pair(base, test, sets, 1, args.threads, args.depth, concurrent)
                    while len(pairs) < args.runs:
                        item = pair(base, test, sets, len(pairs), args.threads, args.depth, concurrent)
                        with open(path, 'a') as f:
                            f.write(json.dumps(item) + '\n')
                            f.flush()
                            os.fsync(f.fileno())
                        pairs.append(item)
                        if len(pairs) % 10 == 0 or len(pairs) == args.runs:
                            print('%3d/%d: cumulative speedup %+.3f%%' %
                                  (len(pairs), args.runs, summarize(pairs)['speedup_pct']), flush=True)
                result = summarize(pairs[:args.runs])
                row = dict(branch=branch, commit=sha, master=master, **result)
                rows.append(row)
                write_summary(work, run, rows)
                print('Speedup: %+.3f%%; geometric 95%% interval: %+.3f%% to %+.3f%%; '
                      'normal P(positive): %.4f' %
                      (result['speedup_pct'], result['geometric_low_95'],
                       result['geometric_high_95'], result['p_positive_normal']), flush=True)
            except (RuntimeError, sp.SubprocessError) as error:
                failures.append(dict(branch=branch, error=str(error)))
                atomic(run / 'failures.json', json.dumps(failures, indent=2))
                print('FAILED: ' + str(error), flush=True)
        if not failures:
            atomic(run / 'failures.json', '[]')
        print('\nFinished: %d successful, %d failed. Summary: %s' %
              (len(rows), len(failures), work / 'summary.csv'), flush=True)
        return bool(failures)


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print('\nStopped. Re-run the same command to resume completed pairs.', flush=True)
        raise SystemExit(130)
