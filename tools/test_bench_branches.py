import contextlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location('runner', Path(__file__).with_name('bench_branches.py'))
r = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(r)


class RunnerTests(unittest.TestCase):
    def test_statistics(self):
        pairs = [dict(pair=i, base=dict(nps=100), test=dict(nps=101)) for i in range(100)]
        result = r.summarize(pairs)
        self.assertAlmostEqual(result['speedup_pct'], 1)
        self.assertAlmostEqual(result['geometric_pct'], 1)
        self.assertEqual(result['p_positive_normal'], 1)
        self.assertEqual(r.summarize([dict(base=dict(nps=100), test=dict(nps=100))])['p_positive_normal'], .5)

    def test_interrupted_append(self):
        with tempfile.TemporaryDirectory() as root:
            p = Path(root) / 'pairs.jsonl'
            p.write_text('{"pair": 0}\n{"pa')
            self.assertEqual(r.load_pairs(p), [{'pair': 0}])
            self.assertEqual(p.read_text(), '{"pair": 0}\n')

    def test_end_to_end_and_resume(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            repo = root / 'fixture'
            repo.mkdir()
            def git(*args):
                return r.command(['git', '-c', 'user.name=Test', '-c', 'user.email=test@example.com', *args], repo)
            git('init', '-b', 'master')
            (repo / 'src').mkdir()
            engine = '#!/usr/bin/env python3\nimport sys\nprint("Nodes searched: 1559611\\nNodes/second: 1000000", file=sys.stderr)\n'
            (repo / 'src/engine').write_text(engine)
            (repo / 'src/Makefile').write_text('profile-build:\n\tcp engine stockfish\n\tchmod +x stockfish\n')
            (repo / '.gitignore').write_text('src/stockfish\n')
            git('add', '.')
            git('commit', '-m', 'base')
            base = git('rev-parse', 'HEAD')
            git('checkout', '-b', 'bench/b01-01-test')
            (repo / 'experiments').mkdir()
            (repo / 'experiments/batch01-candidate.json').write_text(json.dumps(dict(base_commit=base, ready_for_vm_benchmark=True)))
            git('add', '.')
            git('commit', '-m', 'candidate')
            git('branch', 'unrelated-functional-idea')
            git('branch', 'bench/b01-base', base)
            args = ['--repo', str(repo), '--workdir', str(root / 'work'), '--runs', '2', '--sequential']
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertFalse(r.main(args))
            results = list((root / 'work/runs').glob('*/*.jsonl'))
            self.assertEqual(len(results), 1)
            self.assertEqual(len(r.load_pairs(results[0])), 2)
            before = results[0].stat().st_mtime_ns
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertFalse(r.main(args))
            self.assertEqual(results[0].stat().st_mtime_ns, before)
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertFalse(r.main(args[:-1] + ['--sequential', '--runs', '3']))
            self.assertEqual(len(r.load_pairs(results[0])), 3)
            self.assertIn('bench/b01-01-test', (root / 'work/summary.csv').read_text())


if __name__ == '__main__':
    unittest.main()
