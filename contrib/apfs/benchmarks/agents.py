#!/usr/bin/env python3
"""Concurrent real-repository Git agent loops with equally tuned native controls."""
import argparse
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import platform
import random
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
import threading
import time

import bench
import storage

ROOT=bench.ROOT

def percentile(values,q):
    values=sorted(values)
    if not values:return None
    point=(len(values)-1)*q
    lo=int(point);hi=min(lo+1,len(values)-1)
    return values[lo]+(values[hi]-values[lo])*(point-lo)

def diagnostics(stderr):
    rows=[]
    for line in stderr.splitlines():
        if line.startswith('{'):
            try:
                row=json.loads(line)
                if row.get('event')=='git-apfs-checkout':rows.append(row)
            except ValueError:pass
    return rows

def invoke(binary,argv,cwd,env,records,timeout=120):
    env=env.copy();env['PATH']=str(binary.parent)+os.pathsep+env['PATH']
    fd,filename=tempfile.mkstemp(prefix='apfs-rusage-');os.close(fd)
    try:
        result=bench.run(['/usr/bin/time','-l','-o',filename,str(binary),*argv],cwd,env,timeout)
        usage=Path(filename).read_text()
    finally:Path(filename).unlink()
    for name,pattern in [('user_seconds',r'([\d.]+) user'),('system_seconds',r'([\d.]+) sys'),('max_rss_bytes',r'(\d+)\s+maximum resident set size')]:
        match=re.search(pattern,usage)
        result[name]=float(match.group(1)) if match else None
    result['git_argv']=[str(binary),*argv]
    result['apfs']=diagnostics(result['stderr'])
    result['phase']=argv[0] if argv[0]!='worktree' else 'worktree '+argv[1]
    result['worker_leases']=[json.loads(line) for line in result['stderr'].splitlines() if line.startswith('{') and '"event":"git-apfs-worker-lease"' in line]
    records.append(result)
    if result['exit']:raise RuntimeError(f"{argv}: {result['stderr']}")
    return result

def logical_allocation(root):
    # Diagnostic only: st_blocks double-counts CoW extents, never called physical space.
    total=0
    for base,dirs,files in os.walk(root):
        for name in files:
            try:total+=(Path(base)/name).lstat().st_blocks*512
            except FileNotFoundError:pass
    return total

def trial(root,args,variant,agents,repeat,container=None):
    env=bench.environment(root);env['LC_ALL']='C';env['PATH']=str(args.baseline.parent)+os.pathsep+env['PATH']
    env['GIT_APFS_TRACE_JSON']='1'
    if args.profile:env.update(GIT_APFS_PROFILE='1',GIT_TRACE2_PERF='1')
    binary=args.baseline if variant.startswith('native') else args.candidate
    repo=root/'source';records=[];measurements=[];warm_seconds=0
    copied=bench.run([str(args.baseline),'clone','--no-local','--no-checkout',str(args.source),str(repo)],root,env,args.timeout)
    if copied['exit']:raise RuntimeError(copied['stderr'])
    bench.git(repo,env,'checkout','--detach',args.ref)
    bench.git(repo,env,'config','gc.auto','0');bench.git(repo,env,'config','maintenance.auto','false')
    bench.git(repo,env,'config','core.hooksPath','/dev/null')
    base=bench.git(repo,env,'rev-parse','HEAD')
    hash_name=bench.git(repo,env,'rev-parse','--show-object-format')
    # Pick actual tracked text files without modifying fixtures or source repository.
    names=bench.git(repo,env,'ls-files','-z').split('\0')
    candidates=[]
    for name in names:
        p=repo/name
        if not name or p.name=='AGENTS.md' or p.is_symlink() or not p.is_file() or p.stat().st_size>65536:continue
        content=p.read_bytes()
        if b'\0' not in content and p.suffix in {'.c','.h','.py','.ts','.js','.md','.txt','.json'}:candidates.append(name)
    if len(candidates)<args.edits:raise RuntimeError('not enough tracked text files')
    paths=sorted(candidates)[:args.edits]
    expected={p:(repo/p).read_bytes() for p in paths}
    source_before=bench.snapshot(repo)
    def checkpoint(phase):
        row={'phase':phase,'monotonic_seconds':time.monotonic()}
        if container:row.update(storage.allocation(container))
        else:row['summed_st_blocks_not_unique_bytes']=logical_allocation(root)
        measurements.append(row)
    checkpoint('source_fixture')
    if variant.endswith('tuned'):
        bench.git(repo,env,'config','core.fsmonitor','true')
        bench.git(repo,env,'config','core.untrackedCache','true')
    if variant.startswith('apfs-cache'):
        bench.git(repo,env,'config','apfs.cacheLimit',str(args.cache_bytes))
        warm_seconds=invoke(binary,['apfs','cache','warm'],repo,env,records,args.timeout)['seconds']
        checkpoint('cache_warm')
    barrier=threading.Barrier(agents)
    stop=threading.Event();peak=[0]
    def sampler():
        if not container:return
        while not stop.is_set():
            try:
                data=storage.plist(['diskutil','apfs','list','-plist'])
                c=next(c for c in data['Containers'] if c['ContainerReference']==container)
                peak[0]=max(peak[0],c['CapacityCeiling']-c['CapacityFree'])
            except Exception:pass
            stop.wait(.1)
    sampler_thread=threading.Thread(target=sampler,daemon=True);sampler_thread.start()
    start=time.monotonic()
    def agent(i):
        local=[];dest=root/f'agent-{i}';errors=[]
        barrier.wait(timeout=args.timeout)
        try:
            invoke(binary,['worktree','add','-b',f'agent-{i}',str(dest),base],repo,env,local,args.timeout)
            invoke(binary,['status','--porcelain=v1','-z'],dest,env,local,args.timeout)['phase']='first status'
            for cycle in range(args.cycles):
                for p in paths:
                    with (dest/p).open('ab') as f:f.write(f'\n/* agent {i} cycle {cycle} */\n'.encode())
                committed_expected={p:(dest/p).read_bytes() for p in paths}
                invoke(binary,['diff','--stat'],dest,env,local,args.timeout)
                invoke(binary,['add','--',*paths],dest,env,local,args.timeout)
                invoke(binary,['commit','-qm',f'agent {i} cycle {cycle}'],dest,env,local,args.timeout)
                tree=invoke(binary,['ls-tree','-z','HEAD','--',*paths],dest,env,local,args.timeout)
                tree['phase']='verify committed blobs'
                actual={record.split('\t',1)[1]:record.split('\t',1)[0].split()[2] for record in tree['stdout'].split('\0') if record}
                for p,data in committed_expected.items():
                    oid=hashlib.new(hash_name,f'blob {len(data)}\0'.encode()+data).hexdigest()
                    if actual.get(p)!=oid:errors.append('commit omitted edit '+p)
                for p in paths:(dest/p).write_bytes(b'discard this edit\n')
                invoke(binary,['restore','--worktree','--',*paths],dest,env,local,args.timeout)
                for p,data in committed_expected.items():
                    if (dest/p).read_bytes()!=data:errors.append('restore returned wrong bytes '+p)
                if invoke(binary,['status','--porcelain=v1','-z'],dest,env,local,args.timeout)['stdout']:
                    errors.append('restore did not return committed contents')
                    debug=[]
                    for p in paths:
                        data=(dest/p).read_bytes();header=f'blob {len(data)}\0'.encode()
                        debug.append({'path':p,'working_oid':hashlib.sha1(header+data).hexdigest(),'head_oid':bench.git(dest,env,'rev-parse','HEAD:'+p),'mode':oct((dest/p).stat().st_mode&0o777)})
                    local[-1]['dirty_diagnostics']=debug
                    invoke(binary,['diff','--raw'],dest,env,local,args.timeout)
                    invoke(binary,['diff','--cached','--raw'],dest,env,local,args.timeout)
            invoke(binary,['switch','--detach',base],dest,env,local,args.timeout)
            for p in paths:
                if (dest/p).read_bytes()!=expected[p]:errors.append('wrong base bytes '+p)
            if invoke(binary,['status','--porcelain=v1','-z'],dest,env,local,args.timeout)['stdout']:errors.append('base checkout dirty')
            if variant!='native' and args.assert_clones and not variant.startswith('native'):
                if not any(d['cloned'] for c in local for d in c['apfs']):errors.append('clone path unused')
            # Keep all agents' worktrees alive until the retained-allocation checkpoint.
        except Exception as error:errors.append(repr(error))
        return {'agent':i,'commands':local,'errors':errors}
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=agents) as pool:
            rows=list(pool.map(agent,range(agents)))
        wall=time.monotonic()-start
        checkpoint('retained_worktrees')
        cleanup_start=time.monotonic()
        for i in range(agents):
            dest=root/f'agent-{i}'
            if dest.exists():
                # Explicitly stop managed per-worktree monitor daemons before deletion.
                bench.run([str(binary),'fsmonitor--daemon','stop'],dest,env,args.timeout)
                if not (getattr(args,'keep',False) and any(a['errors'] for a in rows)):
                    invoke(binary,['worktree','remove','--force',str(dest)],repo,env,records,args.timeout)
        cleanup_seconds=time.monotonic()-cleanup_start
        checkpoint('after_cleanup')
        if bench.snapshot(repo)!=source_before:raise RuntimeError('source checkout changed')
    finally:
        stop.set();sampler_thread.join(timeout=5)
        bench.run([str(binary),'fsmonitor--daemon','stop'],repo,env,args.timeout)
    commands=[c for row in rows for c in row['commands']]
    lease_events=sorted([event for c in commands for event in c['worker_leases']],key=lambda e:e['at_ns'])
    leased=lease_peak=0
    for event in lease_events:
        leased+=event['delta'];lease_peak=max(lease_peak,leased)
    failures=[e for row in rows for e in row['errors']]
    result={'variant':variant,'agents':agents,'repeat':repeat,'base':base,'source':str(args.source),'tracked_entries':len([n for n in names if n]),'paths':paths,'wall_seconds':wall,'cleanup_wall_seconds':cleanup_seconds,'total_workflow_wall_seconds':wall+cleanup_seconds,'cache_warm_seconds':warm_seconds,
            'agents_results':rows,'maintenance_commands':records,'observed_peak_auxiliary_leases':lease_peak,'lease_balance':leased,'checkpoints':measurements,'peak_sampled_allocated_bytes':peak[0] if container else None,
            'peak_sampling_interval_seconds':.1 if container else None,'outcome':'fail' if failures else 'pass','errors':failures}
    if container:
        if not all(m['stable'] for m in measurements):result['outcome']='fail';result['errors'].append('allocation did not stabilize')
        initial=measurements[0]['allocated_bytes']
        result['retained_extra_bytes']=next(m['allocated_bytes'] for m in measurements if m['phase']=='retained_worktrees')-initial
        result['cleanup_extra_bytes']=measurements[-1]['allocated_bytes']-initial
        result['peak_sampled_extra_bytes']=max(peak[0],max(m['allocated_bytes'] for m in measurements))-initial
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True);p.add_argument('--ref',default='HEAD')
    p.add_argument('--baseline',type=Path,default=ROOT/'benchmark-results/git-baseline/bin/git')
    p.add_argument('--candidate',type=Path,default=ROOT/'benchmark-results/git-apfs/bin/git')
    p.add_argument('--agents',default='1,8,32');p.add_argument('--variants',default='native,apfs,native-tuned,apfs-tuned,apfs-cache,apfs-cache-tuned')
    p.add_argument('--repeats',type=int,default=3);p.add_argument('--cycles',type=int,default=2)
    p.add_argument('--edits',type=int,default=16);p.add_argument('--timeout',type=int,default=240)
    p.add_argument('--mode',choices=['latency','storage'],default='latency')
    p.add_argument('--cache-bytes',type=int,default=64*1024*1024);p.add_argument('--assert-clones',action='store_true')
    p.add_argument('--profile',action='store_true',help='add APFS phase timings and native Trace2 PERF; report separately')
    p.add_argument('--output',type=Path,default=ROOT/'benchmark-results');p.add_argument('--keep',action='store_true')
    args=p.parse_args()
    for name in ('source','baseline','candidate','output'):setattr(args,name,getattr(args,name).resolve())
    levels=[int(n) for n in args.agents.split(',')];variants=args.variants.split(',')
    if min(levels+[args.repeats,args.cycles,args.edits,args.timeout,args.cache_bytes])<1:p.error('counts must be positive')
    if set(variants)-{'native','apfs','native-tuned','apfs-tuned','apfs-cache','apfs-cache-tuned'}:p.error('unknown variant')
    args.output.mkdir(parents=True,exist_ok=True);output=Path(tempfile.mkdtemp(prefix='agents-'+args.mode+'-',dir=args.output))
    report={'schema_version':1,'platform':platform.platform(),'parameters':{k:str(v) if isinstance(v,Path) else v for k,v in vars(args).items()},'executables':{},'results':[]}
    for name in ('baseline','candidate'):
        binary=getattr(args,name);report['executables'][name]={'path':str(binary),'sha256':hashlib.sha256(binary.read_bytes()).hexdigest(),'version':subprocess.check_output([str(binary),'--version'],text=True).strip()}
    report['runner_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    jobs=[(variant,n,r) for variant in variants for n in levels for r in range(args.repeats)];random.Random(0).shuffle(jobs)
    for variant,n,repeat in jobs:
        scratch=Path(tempfile.mkdtemp(prefix=variant+'-',dir=output));attached=False
        try:
            container=None;root=scratch
            if args.mode=='storage':
                image=scratch/'disk.sparseimage';mount=scratch/'mount';mount.mkdir()
                storage.command(['hdiutil','create','-size','16g','-type','SPARSE','-fs','APFS','-nospotlight','-volname','Git-Agent-Loop',image])
                storage.command(['hdiutil','attach','-nobrowse','-noautoopen','-mountpoint',mount,image]);attached=True;root=mount
                (mount/'.metadata_never_index').touch();container=storage.plist(['diskutil','info','-plist',mount])['APFSContainerReference']
            result=trial(root,args,variant,n,repeat,container)
        except Exception as error:result={'variant':variant,'agents':n,'repeat':repeat,'outcome':'fail','errors':[repr(error)]}
        finally:
            if attached:
                try:storage.command(['hdiutil','detach',mount]);attached=False
                except Exception as error:result['errors'].append('detach failed: '+repr(error));result['outcome']='fail'
        report['results'].append(result);(output/'results.json').write_text(json.dumps(report,indent=2)+'\n')
        print(variant,n,repeat,result['outcome'],result['errors'],flush=True)
        if not attached and not args.keep:shutil.rmtree(scratch)
    lines=['# Concurrent real-repository agent loops','','Timings include process launch and /usr/bin/time instrumentation. p95 is descriptive; commands share repositories. CPU/RSS cover the timed command, not the sum of persistent monitor daemons. st_blocks diagnostics are not unique physical allocation. Physical peaks are sampled lower bounds.','', '| Variant | Agents | Active agents wall | Workflow incl. cleanup | Cache warm | Command p50 | Command p95 | Retained extra | Cleanup extra |','| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
    for variant in variants:
        for n in levels:
            rows=[r for r in report['results'] if r['variant']==variant and r['agents']==n and r['outcome']=='pass']
            if not rows:continue
            commands=[c['seconds'] for r in rows for a in r['agents_results'] for c in a['commands']]
            space=lambda key: f"{statistics.median(r[key] for r in rows)/1048576:.2f} MiB" if args.mode=='storage' else 'not measured'
            lines.append(f"| {variant} | {n} | {statistics.median(r['wall_seconds'] for r in rows):.3f}s | {statistics.median(r['total_workflow_wall_seconds'] for r in rows):.3f}s | {statistics.median(r['cache_warm_seconds'] for r in rows):.3f}s | {percentile(commands,.5)*1000:.2f} ms | {percentile(commands,.95)*1000:.2f} ms | {space('retained_extra_bytes')} | {space('cleanup_extra_bytes')} |")
    lines+=['','## Command distributions','', '| Variant | Agents | Command | p50 | p95 | Median CPU | Maximum command RSS |','| --- | ---: | --- | ---: | ---: | ---: | ---: |']
    for variant in variants:
        for n in levels:
            rows=[r for r in report['results'] if r['variant']==variant and r['agents']==n and r['outcome']=='pass']
            commands=[c for r in rows for a in r['agents_results'] for c in a['commands']]
            for phase in sorted(set(c['phase'] for c in commands)):
                cs=[c for c in commands if c['phase']==phase];times=[c['seconds'] for c in cs]
                cpus=[c['user_seconds']+c['system_seconds'] for c in cs if c['user_seconds'] is not None and c['system_seconds'] is not None]
                rss=[c['max_rss_bytes'] for c in cs if c['max_rss_bytes'] is not None]
                cpu=f'{statistics.median(cpus):.3f}s' if cpus else 'unavailable'
                memory=f'{max(rss)/1048576:.2f} MiB' if rss else 'unavailable'
                lines.append(f'| {variant} | {n} | {phase} | {percentile(times,.5)*1000:.2f} ms | {percentile(times,.95)*1000:.2f} ms | {cpu} | {memory} |')
    lines+=['',f"Passed {sum(r['outcome']=='pass' for r in report['results'])}/{len(report['results'])} trials."]
    (output/'summary.md').write_text('\n'.join(lines)+'\n');print('Report:',output)
    return int(any(r['outcome']!='pass' for r in report['results']))
if __name__=='__main__':raise SystemExit(main())
