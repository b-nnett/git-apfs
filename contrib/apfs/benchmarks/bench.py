#!/usr/bin/env python3
"""Isolated APFS worktree correctness and workflow benchmarks (stdlib only)."""
import argparse
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import platform
import random
import signal
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
import threading

ROOT = Path(__file__).resolve().parents[1]
TOOLS = {
    'git': ['git'],
    'apfs-worktree': [str(ROOT / 'benchmark-results/tools/apfs-worktree')],
    'cowtree': [str(ROOT / 'references/cowtree/target/release/cowtree')],
    'simgit': [str(ROOT / 'references/simgit/target/release/simgit')],
    'git-cow': [str(ROOT / 'references/git-cow/target/release/git-cow')],
    'git-worktree-apfs': [str(ROOT / 'references/git-worktree-apfs/git-worktree-apfs')],
    'git-fast-worktree': [str(ROOT / 'references/git-fast-worktree/git-fast-worktree')],
    'gh-wt': [str(ROOT / 'references/gh-wt/gh-wt')],
}
CASES = ['same', 'divergent', 'dirty', 'collision', 'hook', 'warm-build', 'parallel']


def run(argv, cwd, env, timeout=120):
    start = time.perf_counter()
    p = subprocess.Popen([str(a) for a in argv], cwd=cwd, env=env,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         start_new_session=True)
    expired = threading.Event()
    def expire():
        expired.set()
        try:
            os.killpg(p.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    # communicate(timeout=...) finishes with Python's polling waitpid loop.
    # On macOS this can add tens of milliseconds after pipe EOF. Use a
    # blocking wait with an independent watchdog, including descendant cleanup.
    watchdog = threading.Timer(timeout, expire)
    watchdog.daemon = True
    watchdog.start()
    try:
        stdout, stderr = p.communicate()
    finally:
        watchdog.cancel()
    timed_out = expired.is_set()
    return dict(argv=[str(a) for a in argv], seconds=time.perf_counter()-start,
                exit=p.returncode, timeout=timed_out,
                stdout=stdout.decode(errors='replace'), stderr=stderr.decode(errors='replace'))



def git(repo, env, *args):
    result = run(['git', *args], repo, env)
    if result['exit'] != 0:
        raise RuntimeError(f"git {args}: {result['stderr']}")
    return result['stdout'].strip()


def snapshot(path):
    """Content/type/mode snapshot, including ignored files but excluding Git metadata."""
    result = {}
    for base, dirs, files in os.walk(path, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d != '.git')
        for name in sorted(files + [d for d in dirs if (Path(base)/d).is_symlink()]):
            p = Path(base)/name
            if name == '.git':
                continue
            key = str(p.relative_to(path))
            if p.is_symlink():
                result[key] = ['link', os.readlink(p)]
            else:
                result[key] = ['file', p.stat().st_mode & 0o111,
                               hashlib.sha256(p.read_bytes()).hexdigest()]
    return result


def tracked_snapshot(path, env):
    # NUL-delimited paths preserve newlines, Unicode, and Git quoting semantics.
    p = subprocess.run(['git', 'ls-files', '-z'], cwd=path, env=env,
                       check=True, stdout=subprocess.PIPE)
    all_files = snapshot(path)
    return {os.fsdecode(n): all_files.get(os.fsdecode(n)) for n in p.stdout.split(b'\0') if n}


def environment(root):
    env = os.environ.copy()
    for k in list(env):
        if k.startswith('GIT_') or k.startswith('GH_WT_') or k.startswith('SIMGIT_') or k == 'GIT_COW':
            del env[k]
    # Per-run subprocess configuration, never changes the user's HOME or Git config.
    env.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=str(root/'global.gitconfig'),
               GIT_TERMINAL_PROMPT='0', GIT_AUTHOR_NAME='APFS Benchmark',
               GIT_AUTHOR_EMAIL='bench@example.invalid', GIT_COMMITTER_NAME='APFS Benchmark',
               GIT_COMMITTER_EMAIL='bench@example.invalid', XDG_CACHE_HOME=str(root/'cache'),
               GH_WT_NONINTERACTIVE='1', GH_WT_CACHE=str(root/'gh-wt-cache'))
    fallback = ROOT/'benchmark-results/tools/cowtree'
    if fallback.exists():
        env.setdefault('APFS_WORKTREE_COWTREE', str(fallback))
    (root/'global.gitconfig').write_text('')
    return env


def fixture(root, env, files, source=None, file_bytes=1024):
    repo = root/'repo'
    if source:
        r = run(['git', 'clone', '--no-hardlinks', '--no-local', str(source), str(repo)], root, env)
        if r['exit'] != 0:
            raise RuntimeError(r['stderr'])
    else:
        repo.mkdir()
        git(repo, env, 'init', '-q', '-b', 'main')
        for i in range(files):
            p = repo/f'packages/pkg{i % 20:02d}/src/file{i:06d}.txt'
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes((f'export item {i}\n'.encode()+b'payload\n'*((file_bytes//8)+1))[:file_bytes])
        (repo/'space and café.txt').write_text('unusual name\n')
        (repo/'line\nbreak.txt').write_text('newline filename\n')
        (repo/'run.sh').write_text('#!/bin/sh\nexit 0\n')
        (repo/'run.sh').chmod(0o755)
        (repo/'link').symlink_to('space and café.txt')
        (repo/'.gitignore').write_text('node_modules/\n.build/\n.env\n')
        git(repo, env, 'add', '.')
        git(repo, env, 'commit', '-qm', 'fixture baseline')
    baseline = git(repo, env, 'rev-parse', 'HEAD')
    # A divergent branch includes edits, additions and deletion in one commit.
    git(repo, env, 'checkout', '-qb', 'bench-target')
    candidates = sorted(p for p in repo.glob('packages/*/src/*.txt'))
    if candidates:
        for p in candidates[:max(1, len(candidates)//10)]:
            p.write_text(p.read_text()+'target change\n')
        candidates[-1].unlink()
    (repo/'benchmark-added.txt').write_text('target only\n')
    git(repo, env, 'add', '-A')
    git(repo, env, 'commit', '-qm', 'divergent target')
    target = git(repo, env, 'rev-parse', 'HEAD')
    git(repo, env, 'checkout', '--detach', baseline)
    # git-cow expects origin/HEAD even for an entirely local fixture.
    git(repo, env, 'update-ref', 'refs/remotes/origin/bench-base', baseline)
    git(repo, env, 'symbolic-ref', 'refs/remotes/origin/HEAD', 'refs/remotes/origin/bench-base')
    git(repo, env, 'config', 'cow.base', str(root/'cow-template'))
    return repo, baseline, target


def add_command(tool, executable, dest, commit, branch):
    if tool == 'simgit':
        return executable+['add', branch, '--path', str(dest), '--base', commit, '--json']
    if tool == 'git-worktree-apfs':
        return executable+['add', '--new-branch', branch, str(dest), commit]
    if tool == 'gh-wt':
        # Caller creates the requested existing branch; gh-wt has no commit operand.
        return executable+['add', branch, str(dest)]
    prefix = ['worktree', 'add'] if tool == 'git' else ['add']
    return executable+prefix+['-b', branch, str(dest), commit]


def incremental_build(path):
    """Hermetic content-addressed build stand-in, not an actual compiler benchmark."""
    start = time.perf_counter()
    count = 0
    for package in sorted((path/'packages').glob('pkg*')):
        digest = hashlib.sha256()
        for p in sorted(package.glob('src/*.txt')):
            digest.update(p.name.encode()); digest.update(p.read_bytes())
        output = path/'.build'/f'{package.name}.json'
        expected = digest.hexdigest()
        if not output.exists() or output.read_text() != expected:
            output.parent.mkdir(exist_ok=True)
            output.write_text(expected)
            count += 1
    return {'seconds': time.perf_counter()-start, 'rebuilt_packages': count}


def make_hook(root, repo, env):
    hooks = root/'hooks'; hooks.mkdir()
    hook = hooks/'post-checkout'
    hook.write_text('#!/bin/sh\nprintf "%s\\n" "$PWD" >> "$APFS_BENCH_HOOK_LOG"\n')
    hook.chmod(0o755)
    env['APFS_BENCH_HOOK_LOG'] = str(root/'hook-events')
    git(repo, env, 'config', 'core.hooksPath', str(hooks))


def sample(root, tool, executable, case, args):
    env = environment(root)
    repo, baseline, divergent = fixture(root, env, args.files, args.repo, args.file_bytes)
    commit = divergent if case == 'divergent' else baseline
    golden = root/'golden'
    git(repo, env, 'worktree', 'add', '--detach', str(golden), commit)
    expected = tracked_snapshot(golden, env)
    git(repo, env, 'worktree', 'remove', str(golden))
    if case == 'dirty':
        (repo/'benchmark-added.txt').write_text('untracked local work\n')
        if (repo/'space and café.txt').exists():
            (repo/'space and café.txt').write_text('dirty source\n')
    if case == 'warm-build':
        cache = repo/'node_modules/fixture-dependency'
        cache.mkdir(parents=True)
        for i in range(args.dependency_files):
            (cache/f'payload-{i}').write_bytes(b'cache\n'*683)
        (repo/'.env').write_text('BENCHMARK_FAKE_SECRET=must-not-leak\n')
        incremental_build(repo)
    if case == 'hook':
        make_hook(root, repo, env)
    source_before = snapshot(repo)
    records = []
    # Reuse this private repository to measure application-cache warmup, not OS cold cache.
    rounds = args.parallel if case == 'parallel' else 2 if case in ('same', 'warm-build') else 1
    def allocate(i):
        dest = root/f'worktree-{i}'
        branch = f'bench-{i}'
        if tool == 'gh-wt':
            git(repo, env, 'branch', branch, commit)
        if case == 'collision':
            dest.mkdir(); (dest/'sentinel').write_text('preserve this\n')
        before_refs = git(repo, env, 'for-each-ref', '--format=%(refname) %(objectname)')
        before_wt = git(repo, env, 'worktree', 'list', '--porcelain')
        free_before = shutil.disk_usage(root).free
        creation = run(add_command(tool, executable, dest, commit, branch), repo, env, args.timeout)
        free_after = shutil.disk_usage(root).free
        record = dict(index=i, cache_state='fresh-tool-cache' if i == 0 else 'reused-tool-cache',
                      create=creation, volume_free_delta_bytes=free_before-free_after, errors=[])
        record['reported_modes'] = [line for line in creation['stderr'].splitlines() if line.startswith('mode=')]
        if case == 'parallel':
            record['cache_state'] = 'concurrent-shared-cache'
        if case == 'collision':
            if creation['exit'] == 0:
                record['errors'].append('accepted occupied destination')
            if not (dest/'sentinel').exists() or (dest/'sentinel').read_text() != 'preserve this\n':
                record['errors'].append('deleted or changed pre-existing destination')
            record['refs_changed_on_rejection'] = git(repo, env, 'for-each-ref', '--format=%(refname) %(objectname)') != before_refs
            if git(repo, env, 'worktree', 'list', '--porcelain') != before_wt:
                record['errors'].append('rejected allocation changed registrations')
            record['outcome'] = 'fail' if record['errors'] else 'pass'
            return record
        if creation['exit'] != 0:
            after_refs = git(repo, env, 'for-each-ref', '--format=%(refname) %(objectname)')
            after_wt = git(repo, env, 'worktree', 'list', '--porcelain')
            if f'refs/heads/{branch} ' in after_refs and f'refs/heads/{branch} ' not in before_refs:
                record['errors'].append('failed allocation leaked requested branch')
            if 'prunable ' in after_wt and 'prunable ' not in before_wt:
                record['errors'].append('failed allocation leaked stale registration')
            if dest.exists():
                record['errors'].append('failed allocation left destination; inspect recovery state')
            record['outcome'] = 'fail' if record['errors'] else 'rejected'
            return record
        try:
            record['status_first'] = run(['git', 'status', '--porcelain=v1', '-z'], dest, env, args.timeout)
            record['status_second'] = run(['git', 'status', '--porcelain=v1', '-z'], dest, env, args.timeout)
            if record['status_first']['exit'] != 0 or record['status_first']['stdout']:
                record['errors'].append('initial checkout is not clean')
            if git(dest, env, 'rev-parse', 'HEAD') != commit:
                record['errors'].append('wrong HEAD')
            if tracked_snapshot(dest, env) != expected:
                record['errors'].append('tracked bytes/types/modes differ from native checkout')
            if (dest/'.env').exists():
                record['errors'].append('copied ignored fake secret')
            if case == 'hook':
                log = root/'hook-events'
                lines = log.read_text().splitlines() if log.exists() else []
                if lines != [str(dest.resolve())]:
                    record['errors'].append('post-checkout hook missing, repeated, or wrong cwd')
            if case == 'warm-build':
                record['build_first'] = incremental_build(dest)
                record['build_second'] = incremental_build(dest)
                if record['build_second']['rebuilt_packages']:
                    record['errors'].append('incremental build did not reuse its outputs')
                built = snapshot(dest/'.build')
                incremental_build(dest)
                if snapshot(dest/'.build') != built:
                    record['errors'].append('build outputs are unstable')
                record['dependency_cache_present'] = (dest/'node_modules/fixture-dependency/payload-0').exists()
            if args.build_command:
                record['real_build_first'] = run(args.build_command, dest, env, args.timeout)
                record['real_build_second'] = run(args.build_command, dest, env, args.timeout)
                if any(record[k]['exit'] != 0 for k in ('real_build_first', 'real_build_second')):
                    record['errors'].append('real build command failed')
            # Force a same-length content change and restore mtime to challenge stat caching.
            candidates = [dest/name for name, value in expected.items() if value and value[0]=='file' and (dest/name).is_file() and (dest/name).stat().st_size > 0]
            if candidates:
                edit = min(candidates, key=lambda path:path.stat().st_size)
                data = edit.read_bytes()
                stat = edit.stat()
                edit.write_bytes(bytes([data[0] ^ 1])+data[1:])
                os.utime(edit, ns=(stat.st_atime_ns, stat.st_mtime_ns))
                changed = run(['git', 'status', '--porcelain', '-z'], dest, env)
                record['edit_detection'] = changed
                relative = str(edit.relative_to(dest))
                if changed['exit'] != 0 or relative not in changed['stdout']:
                    record['errors'].append('same-size timestamp-preserving edit not detected')
            else:
                record['edit_detection'] = {'skipped':'no nonempty regular tracked file'}
            if snapshot(repo) != source_before:
                record['errors'].append('destination operations changed source checkout')
        except (OSError, RuntimeError, subprocess.SubprocessError) as e:
            record['errors'].append(str(e))
        record['remove'] = run(['git', 'worktree', 'remove', '--force', str(dest)], repo, env, args.timeout)
        if record['remove']['exit'] != 0:
            record['errors'].append('native Git removal failed')
        record['outcome'] = 'fail' if record['errors'] else 'pass'
        return record
    start = time.perf_counter()
    if case == 'parallel':
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.parallel) as pool:
            records = list(pool.map(allocate, range(rounds)))
    else:
        records = [allocate(i) for i in range(rounds)]
    return dict(tool=tool, case=case, wall_seconds=time.perf_counter()-start, allocations=records)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--tools', default=','.join(TOOLS))
    p.add_argument('--tool', action='append', default=[], metavar='NAME=EXECUTABLE')
    p.add_argument('--cases', default=','.join(CASES))
    p.add_argument('--files', type=int, default=2000)
    p.add_argument('--file-bytes', type=int, default=1024)
    p.add_argument('--dependency-files', type=int, default=250)
    p.add_argument('--repeats', type=int, default=3)
    p.add_argument('--parallel', type=int, default=4)
    p.add_argument('--timeout', type=int, default=120)
    p.add_argument('--repo', type=Path, help='local repository; committed HEAD cloned into private fixture')
    p.add_argument('--build-command', type=json.loads, help='JSON argv, e.g. ["npm","test"] (no shell)')
    p.add_argument('--work-dir', type=Path, default=ROOT/'benchmark-results', help='scratch and report parent; choose an APFS volume')
    p.add_argument('--keep', action='store_true', help='retain private fixture repositories for diagnosis')
    args = p.parse_args()
    if min(args.files, args.file_bytes, args.dependency_files, args.repeats, args.parallel, args.timeout) < 1:
        p.error('counts and timeout must be positive')
    if args.build_command is not None and (not isinstance(args.build_command, list) or not args.build_command or not all(isinstance(x,str) for x in args.build_command)):
        p.error('--build-command must be a nonempty JSON string array')
    executables = dict(TOOLS)
    for override in args.tool:
        name, sep, value = override.partition('=')
        if not sep or name not in TOOLS:
            p.error('tool override must be NAME=EXECUTABLE for a known tool')
        executables[name] = [str(Path(value).resolve()) if '/' in value else value]
    selected = args.tools.split(','); cases = args.cases.split(',')
    if set(selected)-set(TOOLS) or set(cases)-set(CASES):
        p.error('unknown tool or case')
    if args.repo:
        args.repo = args.repo.resolve()
    args.work_dir.mkdir(parents=True, exist_ok=True)
    output = Path(tempfile.mkdtemp(prefix='run-', dir=args.work_dir.resolve()))
    report = dict(schema_version=1, host=dict(platform=platform.platform(), python=sys.version,
                  git=subprocess.check_output(['git','--version'],text=True).strip()),
                  parameters=vars(args).copy(), skipped=[], results=[])
    report['parameters'] = {k:str(v) if isinstance(v,Path) else v for k,v in report['parameters'].items()}
    report['disk_info'] = run(['diskutil','info',str(output)], ROOT, os.environ.copy()) if shutil.which('diskutil') else None
    report['reference_revisions'] = json.loads((ROOT/'references.lock.json').read_text())
    jobs = [(t,c,r) for t in selected for c in cases for r in range(args.repeats)]
    random.Random(0).shuffle(jobs)
    unavailable = {t for t in selected if not shutil.which(executables[t][0])}
    report['skipped'] = [{'tool':t,'reason':'executable unavailable','executable':executables[t]} for t in sorted(unavailable)]
    report['executables'] = {}
    for tool in selected:
        if tool in unavailable:
            continue
        path = Path(shutil.which(executables[tool][0])).resolve()
        try:
            probe = run(executables[tool]+['--help'], output, environment(output), 10)
            report['executables'][tool] = {'path':str(path), 'sha256':hashlib.sha256(path.read_bytes()).hexdigest(), 'probe':probe}
            if probe['exit'] < 0 or probe['exit'] in (126,127) or probe['timeout']:
                unavailable.add(tool)
                report['skipped'].append({'tool':tool,'reason':'startup probe failed; see executables diagnostics'})
        except OSError as e:
            unavailable.add(tool)
            report['skipped'].append({'tool':tool,'reason':str(e)})
    for t,c,r in jobs:
        if t in unavailable:
            continue
        scratch = Path(tempfile.mkdtemp(prefix=f'{t}-{c}-{r}-', dir=output))
        try:
            result = sample(scratch,t,executables[t],c,args)
        except Exception as e:
            result = dict(tool=t,case=c,error=repr(e),allocations=[])
        result['repeat'] = r
        report['results'].append(result)
        print(f"{t:20} {c:12} " + ', '.join(a['outcome'] for a in result['allocations']) + result.get('error',''), flush=True)
        if not args.keep:
            shutil.rmtree(scratch)
        (output/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    groups = {}
    for result in report['results']:
        key = (result['tool'],result['case'])
        group = groups.setdefault(key,[])
        group.extend(result['allocations'])
    lines = ['# Worktree benchmark results','', '| Tool | Case | Pass / fail / rejected | Median add | First status | First build | Remove |','| --- | --- | --- | --- | --- | --- | --- |']
    for (tool,case),rows in sorted(groups.items()):
        counts = [sum(a['outcome']==s for a in rows) for s in ('pass','fail','rejected')]
        values = [a['create']['seconds'] for a in rows if a['outcome']=='pass']
        timing = f'{statistics.median(values):.4f}s' if values else '—'
        def phase(name):
            values = [a[name]['seconds'] for a in rows if a['outcome']=='pass' and name in a]
            return f'{statistics.median(values):.4f}s' if values else '—'
        build = 'real_build_first' if args.build_command else 'build_first'
        lines.append(f"| {tool} | {case} | {' / '.join(map(str,counts))} | {timing} | {phase('status_first')} | {phase(build)} | {phase('remove')} |")
    lines += ['', 'Medians include passing allocations only. Inspect fresh/reused samples separately in JSON.',
              'Times are wall clock. Fresh/reused refer to tool caches, not flushed OS caches.',
              'Volume free-space deltas are noisy diagnostics, not attributed CoW savings.',
              'See results.json for phase timings, commands, failures, host and skipped tools.']
    for skip in report['skipped']:
        lines.append(f"\nSkipped {skip['tool']}: {skip['reason']}.")
    (output/'summary.md').write_text('\n'.join(lines)+'\n')
    (output/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    print(f'Report: {output}')
    if not report['results']:
        return 2
    return 1 if any(r.get('error') or any(a['outcome']=='fail' for a in r['allocations']) for r in report['results']) else 0

if __name__ == '__main__':
    sys.exit(main())
