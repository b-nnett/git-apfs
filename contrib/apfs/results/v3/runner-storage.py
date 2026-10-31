#!/usr/bin/env python3
"""Measure marginal physical APFS container allocation on private disk images."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import plistlib
import random
import shutil
import statistics
import subprocess
import tempfile
import time

import bench


def command(argv):
    return subprocess.check_output([str(a) for a in argv], stderr=subprocess.PIPE)


def plist(argv):
    return plistlib.loads(command(argv))


def allocation(container):
    """Wait for three identical post-sync container allocation readings."""
    samples = []
    for _ in range(15):
        os.sync()
        data = plist(['diskutil', 'apfs', 'list', '-plist'])
        matching = [c for c in data['Containers'] if c['ContainerReference'] == container]
        if len(matching) != 1:
            raise RuntimeError('private APFS container disappeared')
        c = matching[0]
        used = c['CapacityCeiling']-c['CapacityFree']
        samples.append(used)
        if len(samples) >= 3 and len(set(samples[-3:])) == 1:
            return {'allocated_bytes':used, 'stable':True, 'samples':samples}
        time.sleep(.2)
    return {'allocated_bytes':samples[-1], 'stable':False, 'samples':samples}


def trial(output, tool, executable, files, size, count, repeat, lifecycle=False, compact_binary=None):
    scratch = Path(tempfile.mkdtemp(prefix=f'{tool}-{files}-{repeat}-', dir=output))
    image = scratch/'volume.sparseimage'
    mount = scratch/'mount'; mount.mkdir()
    attached = False
    result = dict(tool=tool, files=files, file_bytes=size, worktrees=count, repeat=repeat, stages=[], errors=[])
    try:
        command(['hdiutil','create','-size','4g','-type','SPARSE','-fs','APFS',
                 '-volname','APFS-Worktree-Bench','-nospotlight',image])
        info = plist(['hdiutil','attach','-plist','-nobrowse','-noautoopen','-mountpoint',mount,image])
        attached = True
        volume = plist(['diskutil','info','-plist',mount])
        container = volume['APFSContainerReference']
        result['volume_info'] = volume
        # The fresh private container has no user snapshots or unrelated writers.
        (mount/'.metadata_never_index').touch()
        result['container'] = container
        result['empty'] = allocation(container)
        env = bench.environment(mount)
        repo, _, _ = bench.fixture(mount, env, files, file_bytes=size)
        # Deterministic incompressible tracked payload; don't mistake compression
        # or tiny-file slack for clone sharing. Commit source setup before measuring.
        rng = random.Random(123)
        payloads = sorted(repo.glob('packages/*/src/*.txt'))
        for path in payloads:
            path.write_bytes(rng.randbytes(size))
        bench.git(repo,env,'add','-A')
        bench.git(repo,env,'commit','-qm','incompressible storage fixture')
        commit = bench.git(repo,env,'rev-parse','HEAD')
        expected = bench.tracked_snapshot(repo,env)
        source_hash = bench.snapshot(repo)
        before = allocation(container)
        result['fixture'] = before
        result['tracked_payload_bytes'] = files*size
        for i in range(count):
            dest = mount/f'worktree-{i}'
            creation = bench.run(bench.add_command(tool,executable,dest,commit,f'storage-{i}'),repo,env,120)
            status = bench.run(['git','status','--porcelain'],dest,env,120) if creation['exit']==0 else None
            if creation['exit'] != 0:
                raise RuntimeError(f"creation failed: {creation}")
            if status['exit'] != 0 or status['stdout'] or bench.tracked_snapshot(dest,env)!=expected:
                result['errors'].append(f'incorrect checkout {i}')
            measured = allocation(container)
            result['stages'].append({'count':i+1,'allocation':measured,
                'marginal_bytes':measured['allocated_bytes']-before['allocated_bytes'],
                'create':creation,'first_status':status})
        # Independently rewrite approximately 10% of files in every worktree, preserving source.
        # Full file rewrites model generated assets/rebuilt artifacts, not a single-byte edit.
        start = time.perf_counter()
        for i in range(count):
            dest = mount/f'worktree-{i}'
            mutate = random.Random(1000+i)
            for original in payloads[:max(1,files//10)]:
                (dest/original.relative_to(repo)).write_bytes(mutate.randbytes(size))
        after_edits = allocation(container)
        result['after_10_percent_rewrites'] = dict(allocation=after_edits,
            marginal_bytes=after_edits['allocated_bytes']-before['allocated_bytes'],
            seconds=time.perf_counter()-start)
        if lifecycle:
            result['git_commands']=[]
            changed=[bench.tracked_snapshot(mount/f'worktree-{i}',env) for i in range(count)]
            heads=[]
            def step(name, argv, cwd):
                recorded=bench.run(['git']+argv,cwd,env,120)
                recorded['phase']=name
                result['git_commands'].append(recorded)
                if recorded['exit']!=0:
                    raise RuntimeError(f"{name} failed: {recorded['stderr']}")
            for i in range(count):
                dest=mount/f'worktree-{i}'
                step('add',['add','-u'],dest)
                step('commit',['commit','-m','benchmark: independent edits'],dest)
                heads.append(bench.git(dest,env,'rev-parse','HEAD'))
                if bench.git(dest,env,'rev-parse','HEAD^')!=commit:
                    result['errors'].append('lifecycle commit has wrong parent')
                if bench.tracked_snapshot(dest,env)!=changed[i]:
                    result['errors'].append('lifecycle commit changed checkout bytes')
            measured=allocation(container)
            result['after_commit']={'allocation':measured,'marginal_bytes':measured['allocated_bytes']-before['allocated_bytes']}
            for i in range(count):
                dest=mount/f'worktree-{i}'
                step('switch-base',['switch','--detach',commit],dest)
                if bench.tracked_snapshot(dest,env)!=expected:
                    result['errors'].append('switch-base produced wrong bytes')
            measured=allocation(container)
            result['after_switch_base']={'allocation':measured,'marginal_bytes':measured['allocated_bytes']-before['allocated_bytes']}
            if compact_binary:
                for i in range(count):
                    dest=mount/f'worktree-{i}'
                    recorded=bench.run([str(compact_binary),'compact','--source',str(repo),str(dest)],repo,env,120)
                    recorded['phase']='compact-base'
                    result['git_commands'].append(recorded)
                    if recorded['exit']!=0:
                        raise RuntimeError(f"compaction failed: {recorded['stderr']}")
                    if bench.tracked_snapshot(dest,env)!=expected or bench.git(dest,env,'rev-parse','HEAD')!=commit:
                        result['errors'].append('compaction changed base bytes or HEAD')
                measured=allocation(container)
                result['after_compact_base']={'allocation':measured,'marginal_bytes':measured['allocated_bytes']-before['allocated_bytes']}

            for i in range(count):
                dest=mount/f'worktree-{i}'
                step('switch-agent',['switch',f'storage-{i}'],dest)
                if bench.git(dest,env,'rev-parse','HEAD')!=heads[i] or bench.tracked_snapshot(dest,env)!=changed[i]:
                    result['errors'].append('switch-agent produced wrong commit or bytes')
            measured=allocation(container)
            result['after_switch_agent']={'allocation':measured,'marginal_bytes':measured['allocated_bytes']-before['allocated_bytes']}
        if bench.snapshot(repo)!=source_hash:
            result['errors'].append('worktree writes changed source')
        for i in range(count):
            bench.git(repo,env,'worktree','remove','--force',str(mount/f'worktree-{i}'))
        result['after_removal'] = allocation(container)
        result['remaining_delta_bytes'] = result['after_removal']['allocated_bytes']-before['allocated_bytes']
        result['empty_to_fixture_bytes'] = before['allocated_bytes']-result['empty']['allocated_bytes']
    except Exception as e:
        result['errors'].append(repr(e))
    finally:
        if attached:
            try:
                command(['hdiutil','detach',mount])
                attached = False
            except subprocess.CalledProcessError as e:
                result['errors'].append(f'detach failed: {e}; retained {scratch}')
        if not attached:
            shutil.rmtree(scratch)
    # diskutil includes datetime/bytes on some OS releases; JSON default=str below.
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--cowtree',type=Path,default=bench.ROOT/'benchmark-results/tools/cowtree')
    p.add_argument('--candidate',type=Path,help='also measure the experimental apfs-worktree binary')
    p.add_argument('--repeats',type=int,default=3)
    p.add_argument('--worktrees',type=int,default=4)
    p.add_argument('--profiles',default='small,large',help='comma-separated small,large fixture profiles')
    p.add_argument('--compact-after-switch',action='store_true',help='experiment: verified cowtree compaction after switching to base')
    p.add_argument('--git-lifecycle',action='store_true',help='also measure allocation after commits and branch switches')
    p.add_argument('--tools',help='comma-separated subset: git,cowtree,apfs-worktree')
    p.add_argument('--output',type=Path,default=bench.ROOT/'benchmark-results')
    args=p.parse_args()
    if args.repeats<1 or args.worktrees<1:
        p.error('counts must be positive')
    if not shutil.which('hdiutil') or not shutil.which('diskutil'):
        p.error('requires macOS hdiutil and diskutil')
    if not args.cowtree.is_file():
        p.error('supply --cowtree /path/to/cowtree')
    if args.compact_after_switch and not args.git_lifecycle:
        p.error('--compact-after-switch requires --git-lifecycle')
    profiles={'small':(2000,4096),'large':(128,1048576)}
    selected_profiles=args.profiles.split(',')
    if set(selected_profiles)-set(profiles):p.error('unknown profile')
    shapes=[profiles[name] for name in selected_profiles]
    args.output.mkdir(parents=True,exist_ok=True)
    output=Path(tempfile.mkdtemp(prefix='storage-',dir=args.output.resolve()))
    tools={'git':['git'],'cowtree':[str(args.cowtree.resolve())]}
    if args.candidate:
        tools['apfs-worktree']=[str(args.candidate.resolve())]
    if args.tools:
        selected=args.tools.split(',')
        if set(selected)-set(tools):
            p.error('unknown tool or missing --candidate')
        tools={name:tools[name] for name in selected}
    report={'schema_version':1,'host':{'platform':bench.platform.platform(),'git':command(['git','--version']).decode().strip()},'measurement':'APFS container CapacityCeiling minus CapacityFree on private sparse images',
        'results':[], 'cowtree_sha256':hashlib.sha256(args.cowtree.read_bytes()).hexdigest()}
    report['executables']={name:{'path':str(Path(shutil.which(argv[0])).resolve()),'sha256':hashlib.sha256(Path(shutil.which(argv[0])).read_bytes()).hexdigest()} for name,argv in tools.items()}
    jobs=[(t,n,size,r) for t in tools for n,size in shapes for r in range(args.repeats)]
    random.Random(0).shuffle(jobs)
    for tool,n,size,r in jobs:
        os.environ['APFS_WORKTREE_COWTREE']=str(args.cowtree.resolve())
        result=trial(output,tool,tools[tool],n,size,args.worktrees,r,args.git_lifecycle,args.cowtree.resolve() if args.compact_after_switch else None)
        report['results'].append(result)
        (output/'results.json').write_text(json.dumps(report,indent=2,default=str)+'\n')
        print(tool,n,size,'errors:',result['errors'],flush=True)
    lines=['# Physical APFS storage comparison','',
        'Fresh private APFS containers; median over repetitions. Allocation includes filesystem and Git metadata. Source checkout and Git objects are present before marginal measurement.', '',
        '| Fixture | Tool | Added worktrees | Initial added allocation | After ~10% rewrites | Total source + Git + worktrees | Create + first status per worktree |',
        '| --- | --- | --- | --- | --- | --- | --- |']
    for n,size in shapes:
        for tool in tools:
            rows=[r for r in report['results'] if r['tool']==tool and r['files']==n and not r['errors']]
            if not rows:
                continue
            med=lambda vals:statistics.median(vals)
            initial=med([r['stages'][-1]['marginal_bytes'] for r in rows])/1048576
            edited=med([r['after_10_percent_rewrites']['marginal_bytes'] for r in rows])/1048576
            total=med([r['empty_to_fixture_bytes']+r['stages'][-1]['marginal_bytes'] for r in rows])/1048576
            seconds=med([s['create']['seconds']+s['first_status']['seconds'] for r in rows for s in r['stages']])
            lines.append(f'| {n} × {size} bytes | {tool} | {args.worktrees} | {initial:.2f} MiB | {edited:.2f} MiB | {total:.2f} MiB | {seconds:.3f}s |')
    if args.git_lifecycle:
        lines+=['','## Git lifecycle allocation','',
                'Marginal container allocation, including new Git objects and baseline caches; four live worktrees by default.', '',
                '| Files | Tool | After commits | After switch to base | After switch back |',
                '| --- | --- | --- | --- | --- |']
        for n in (2000,128):
            for tool in tools:
                rows=[r for r in report['results'] if r['tool']==tool and r['files']==n and not r['errors']]
                if rows:
                    values=[statistics.median(r[key]['marginal_bytes'] for r in rows)/1048576 for key in ('after_commit','after_switch_base','after_switch_agent')]
                    lines.append(f"| {n} | {tool} | "+' | '.join(f'{v:.2f} MiB' for v in values)+' |')
    if args.compact_after_switch:
        lines+=['','## Verified re-sharing experiment','',
                '| Files | Tool | Before compaction at base | After compaction at base |',
                '| --- | --- | --- | --- |']
        for n,_ in shapes:
            for tool in tools:
                rows=[r for r in report['results'] if r['tool']==tool and r['files']==n and not r['errors']]
                if rows:
                    before_bytes=statistics.median(r['after_switch_base']['marginal_bytes'] for r in rows)/1048576
                    after_bytes=statistics.median(r['after_compact_base']['marginal_bytes'] for r in rows)/1048576
                    lines.append(f'| {n} | {tool} | {before_bytes:.2f} MiB | {after_bytes:.2f} MiB |')
    unstable=[r for r in report['results'] if any(not x['allocation']['stable'] for x in r['stages'])]
    lines+=['',f'Runs with unstable allocation checkpoints: {len(unstable)}. Inspect raw samples in results.json.',
        'This measures container block allocation, not logical du size or sparse-image host-file length. It includes bookkeeping, does not isolate individual extents, and does not measure device write amplification.',
        'Image-backed timing is secondary: use the separate native-volume workflow suite for primary latency measurements. All worktrees are retained together until the rewrite phase; caches/metadata are included. No OS cache flush is performed.']
    (output/'summary.md').write_text('\n'.join(lines)+'\n')
    print(f'Report: {output}')
    return int(any(r['errors'] for r in report['results']))

if __name__=='__main__':
    raise SystemExit(main())
