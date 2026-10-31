#!/usr/bin/env python3
"""Matched native Git vs Git APFS switch/restore timings and physical allocation."""
import argparse
import copy
import hashlib
import json
import os
import platform
from pathlib import Path
import random
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
import time

import bench
import storage

ROOT=bench.ROOT
BINARY_ENV={}

def run_git(binary,argv,cwd,env,timeout=120):
    local=env.copy();local['PATH']=str(binary.parent)+os.pathsep+env['PATH']
    local.update(BINARY_ENV.get(str(binary),{}))
    result=bench.run([str(binary),*argv],cwd,local,timeout)
    if result['exit']!=0:raise RuntimeError(f"{argv}: {result['stderr']}")
    matches=re.findall(r'git-apfs: attempted=(\d+) cloned=(\d+) bytes=(\d+)',result['stderr'])
    result['cloned_files']=sum(int(m[1]) for m in matches)
    result['cloned_logical_bytes']=sum(int(m[2]) for m in matches)
    return result


def trial(root,variant,operation,files,size,args,container=None):
    baseline=args.baseline;candidate=args.candidate
    env=bench.environment(root);env['PATH']=str(baseline.parent)+os.pathsep+env['PATH'];env['LC_ALL']='C'
    repo,_,_=bench.fixture(root,env,files,file_bytes=size)
    bench.git(repo,env,'config','gc.auto','0')
    rng=random.Random(123)
    payloads=sorted(repo.glob('packages/*/src/*.txt'))
    for path in payloads:path.write_bytes(rng.randbytes(size))
    bench.git(repo,env,'add','-A');bench.git(repo,env,'commit','-qm','incompressible base')
    base=bench.git(repo,env,'rev-parse','HEAD')
    expected=bench.tracked_snapshot(repo,env);source=bench.snapshot(repo)
    result={'variant':variant,'operation':operation,'files':files,'file_bytes':size,
            'worktrees':args.worktrees,'base':base,'commands':[],'setup':[],'errors':[]}
    if container:result['fixture_allocation']=storage.allocation(container)
    count=max(1,files//10)
    result['changed_paths_per_worktree']=count
    changed_paths=[str(p.relative_to(repo)) for p in payloads[:count]]
    targets=[];index_before=[];expected_targets=[]
    target_variants=[variant]*args.worktrees
    if variant=='paired':
        target_variants=[v for _ in range(args.worktrees) for v in ('native','apfs')]
        random.Random(args.pair_seed).shuffle(target_variants)
    result['target_variants']=target_variants
    for i in range(len(target_variants)):
        dest=root/f'agent-{i}';targets.append(dest)
        # Both arms start with identically shared files. This isolates switch and
        # restore from the already-measured worktree creation improvement.
        setup_env=env.copy();setup_env['GIT_APFS_TRACE']='1';setup_env['GIT_APFS_CLONE_CHECKOUT']='1'
        setup=run_git(candidate,['worktree','add','-b',f'agent-{i}',str(dest),base],repo,setup_env,args.timeout)
        result['setup'].append(setup)
        if setup['cloned_files']==0:raise RuntimeError('setup did not create shared worktrees')
        mutate=random.Random(1000+i)
        for path in changed_paths:(dest/path).write_bytes(mutate.randbytes(size))
        wanted=dict(expected)
        if operation=='switch':
            bench.git(dest,env,'add','-u');bench.git(dest,env,'commit','-qm','agent edits')
        else:
            unrelated='space and café.txt';data=f'keep staged {i}\n'.encode()
            (dest/unrelated).write_bytes(data);bench.git(dest,env,'add','--',unrelated)
            wanted[unrelated]=['file',0,hashlib.sha256(data).hexdigest()]
            (dest/'agent-note').write_text(f'keep untracked {i}\n')
        index_before.append(bench.git(dest,env,'ls-files','--stage','-z'))
        expected_targets.append(wanted)
    # Optional, explicit workload profile: let setup timestamps leave Git's
    # same-second racy-index window. This is not an OS-cache flush.
    if args.settle_seconds:
        time.sleep(args.settle_seconds)
    if container:result['before']=storage.allocation(container)
    command_env=env.copy();command_env['GIT_APFS_TRACE']='1'
    for dest,target_variant in zip(targets,target_variants):
        binary=baseline if target_variant=='native' else candidate
        command_env['GIT_APFS_CLONE_CHECKOUT']='0' if target_variant=='disabled' else '1'
        argv=['switch','--detach',base] if operation=='switch' else ['restore','--worktree','--',*changed_paths]
        command=run_git(binary,argv,dest,command_env,args.timeout)
        status=run_git(binary,['status','--porcelain=v1','-z'],dest,command_env,args.timeout)
        result['commands'].append({'variant':target_variant,'operation':command,'first_status':status})
    if container:
        result['after']=storage.allocation(container)
        fixture=result['fixture_allocation']['allocated_bytes']
        result['before_extra_bytes']=result['before']['allocated_bytes']-fixture
        result['after_extra_bytes']=result['after']['allocated_bytes']-fixture
        result['operation_delta_bytes']=result['after']['allocated_bytes']-result['before']['allocated_bytes']
    for i,dest in enumerate(targets):
        target_variant=target_variants[i]
        binary=baseline if target_variant=='native' else candidate
        command_env['GIT_APFS_CLONE_CHECKOUT']='0' if target_variant=='disabled' else '1'
        if bench.tracked_snapshot(dest,env)!=expected_targets[i]:result['errors'].append(f'wrong checkout bytes/types/modes at {dest.name}')
        if bench.git(dest,env,'rev-parse','HEAD')!=base:result['errors'].append(f'wrong HEAD at {dest.name}')
        if operation=='restore':
            if bench.git(dest,env,'ls-files','--stage','-z')!=index_before[i]:result['errors'].append('restore changed index entries')
            if (dest/'agent-note').read_text()!=f'keep untracked {i}\n':result['errors'].append('untracked note changed')
        elif result['commands'][i]['first_status']['stdout']:result['errors'].append('switch result is dirty')
        # Directly modify an existing file and restore its mtime. No fresh probe
        # commit is allowed to mask coarse-timestamp/index regressions.
        path=dest/changed_paths[0];old=path.stat();data=path.read_bytes()
        path.write_bytes(bytes([data[0]^1])+data[1:]);os.utime(path,ns=(old.st_atime_ns,old.st_mtime_ns))
        status=run_git(binary,['status','--porcelain=v1','-z'],dest,command_env,args.timeout)
        if changed_paths[0]+'\0' not in status['stdout']:result['errors'].append('timestamp-preserving edit was hidden')
    if bench.snapshot(repo)!=source:result['errors'].append('donor checkout changed')
    if any(c['variant']=='apfs' and not c['operation']['cloned_files'] for c in result['commands']):
        result['errors'].append('APFS checkout fast path was not exercised')
    if variant=='disabled' and any(c['operation']['cloned_files'] for c in result['commands']):
        result['errors'].append('disabled control unexpectedly cloned files')
    result['outcome']='fail' if result['errors'] else 'pass'
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--baseline',type=Path,default=ROOT/'benchmark-results/git-baseline/bin/git')
    p.add_argument('--candidate',type=Path,default=ROOT/'benchmark-results/git-apfs/bin/git')
    p.add_argument('--mode',choices=['latency','storage'],default='latency')
    p.add_argument('--profiles',default='small,large')
    p.add_argument('--operations',default='switch,restore')
    p.add_argument('--variants',default='native,apfs',help='native,apfs and optional disabled control')
    p.add_argument('--worktrees',type=int,default=4)
    p.add_argument('--candidate-workers',type=int,help='explicit checkout.workers control for the candidate only')
    p.add_argument('--paired',action='store_true',help='latency only: interleave native/APFS worktrees in one shared fixture')
    p.add_argument('--repeats',type=int,default=3)
    p.add_argument('--settle-seconds',type=float,default=0,help='untimed idle period before commands; 1.1 tests settled timestamp state')
    p.add_argument('--timeout',type=int,default=120)
    p.add_argument('--output',type=Path,default=ROOT/'benchmark-results')
    p.add_argument('--keep',action='store_true')
    args=p.parse_args()
    args.baseline=args.baseline.resolve();args.candidate=args.candidate.resolve()
    if args.candidate_workers is not None:
        if args.candidate_workers<0:p.error('--candidate-workers must be nonnegative')
        BINARY_ENV[str(args.candidate)]={'GIT_CONFIG_COUNT':'1','GIT_CONFIG_KEY_0':'checkout.workers','GIT_CONFIG_VALUE_0':str(args.candidate_workers)}
    if not args.baseline.is_file() or not args.candidate.is_file():p.error('run python3 native/build.py first')
    if args.paired and (args.mode!='latency' or args.variants!='native,apfs'):p.error('--paired requires latency mode and native,apfs variants')
    if args.settle_seconds<0:p.error('--settle-seconds must be nonnegative')
    if min(args.worktrees,args.repeats,args.timeout)<1:p.error('counts must be positive')
    shapes={'small':(2000,4096),'large':(128,1048576),'smoke':(20,128)}
    profiles=args.profiles.split(',');operations=args.operations.split(',');variants=args.variants.split(',')
    if set(profiles)-set(shapes) or set(operations)-{'switch','restore'} or set(variants)-{'native','apfs','disabled'}:p.error('unknown profile, operation or variant')
    args.output.mkdir(parents=True,exist_ok=True)
    output=Path(tempfile.mkdtemp(prefix=f'checkout-{args.mode}-',dir=args.output.resolve()))
    report={'schema_version':2,'runner':{'method':'blocking-communicate-with-process-group-watchdog','bench_sha256':hashlib.sha256(Path(bench.__file__).read_bytes()).hexdigest(),'checkout_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},'host':{'platform':platform.platform()},'parameters':{k:str(v) if isinstance(v,Path) else v for k,v in vars(args).items()},'executables':{},'results':[]}
    for name,binary in [('native',args.baseline),('apfs',args.candidate)]:
        report['executables'][name]={'path':str(binary),'sha256':hashlib.sha256(binary.read_bytes()).hexdigest(),'version':subprocess.check_output([str(binary),'--version'],text=True).strip()}
    jobs=[(variant,operation,profile,r) for variant in (['paired'] if args.paired else variants) for operation in operations for profile in profiles for r in range(args.repeats)]
    random.Random(0).shuffle(jobs)
    for variant,operation,profile,repeat in jobs:
        scratch=Path(tempfile.mkdtemp(prefix=f'{variant}-{operation}-{profile}-',dir=output));attached=False
        image=scratch/'disk.sparseimage';mount=scratch/'mount';mount.mkdir()
        try:
            container=None;root=scratch
            if args.mode=='storage':
                storage.command(['hdiutil','create','-size','4g','-type','SPARSE','-fs','APFS','-nospotlight','-volname','Git-APFS-checkout',image])
                storage.command(['hdiutil','attach','-nobrowse','-noautoopen','-mountpoint',mount,image]);attached=True
                (mount/'.metadata_never_index').touch()
                info=storage.plist(['diskutil','info','-plist',mount]);container=info['APFSContainerReference'];root=mount
            args.pair_seed=repeat
            result=trial(root,variant,operation,*shapes[profile],args,container)
        except Exception as e:
            result={'variant':variant,'operation':operation,'outcome':'fail','errors':[repr(e)],'commands':[]}
        finally:
            if attached:
                try:storage.command(['hdiutil','detach',mount]);attached=False
                except Exception as e:result['errors'].append(f'detach failed, retained {scratch}: {e}');result['outcome']='fail'
        result.update(profile=profile,repeat=repeat)
        if variant=='paired':
            for member in variants:
                split=copy.deepcopy(result)
                split.update(variant=member,pair_id=f'{profile}-{operation}-{repeat}')
                split['commands']=[c for c in split['commands'] if c['variant']==member]
                report['results'].append(split)
        else:
            report['results'].append(result)
        (output/'results.json').write_text(json.dumps(report,indent=2)+'\n')
        print(variant,operation,profile,repeat,result['outcome'],result['errors'],flush=True)
        if not attached and not args.keep:shutil.rmtree(scratch)
    lines=['# Native Git vs Git APFS checkout','',
           f'Paired latency fixtures: {args.paired}. Automatic Git GC is disabled in the fixture for both variants to exclude background maintenance.', '',
           f'Untimed settling period: {args.settle_seconds}s. Matched upstream/fork builds. Both arms begin with identically APFS-shared worktrees. Changes are ~10% of files. Timings include the whole Git process; first status is separate. No post-command compaction.', '',
           '| Profile | Command | Variant | Git command median | Command + first status | Extra allocation after operation |','| --- | --- | --- | --- | --- | --- |']
    for profile in profiles:
        for operation in operations:
            for variant in variants:
                rows=[r for r in report['results'] if r['profile']==profile and r['operation']==operation and r['variant']==variant and r['outcome']=='pass']
                if not rows:continue
                commands=[c for r in rows for c in r['commands']]
                command=statistics.median(c['operation']['seconds'] for c in commands)*1000
                total=statistics.median(c['operation']['seconds']+c['first_status']['seconds'] for c in commands)*1000
                space=f"{statistics.median(r['after_extra_bytes'] for r in rows)/1048576:.2f} MiB" if args.mode=='storage' else 'not measured'
                lines.append(f'| {profile} | {operation} | {variant} | {command:.2f} ms | {total:.2f} ms | {space} |')
    lines+=['',f"Passed {sum(r['outcome']=='pass' for r in report['results'])}/{len(report['results'])} trials.",
            'Physical allocation includes Git objects, refs and index metadata relative to the source fixture, not logical du sizes. Storage trials use private APFS containers; latency trials use the host filesystem. Four worktrees per variant; paired latency keeps eight worktrees live in one fixture.',
            'Checks: bytes/types/modes, HEAD, preserved restore index entries and unrelated staged/untracked work, source isolation, restored-mtime edit detection, and actual clone counters.']
    (output/'summary.md').write_text('\n'.join(lines)+'\n')
    print(f'Report: {output}')
    return int(any(r['outcome']=='fail' for r in report['results']))

if __name__=='__main__':raise SystemExit(main())
