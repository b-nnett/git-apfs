#!/usr/bin/env python3
"""Build matched upstream Git and the native Git APFS fork into local prefixes."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import subprocess
import tarfile
import tempfile

ROOT=Path(__file__).resolve().parents[1]

def run(argv,cwd=None,env=None):
    subprocess.run([str(a) for a in argv],cwd=cwd,env=env,check=True)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--jobs',type=int,default=4)
    p.add_argument('--output',type=Path,default=ROOT/'benchmark-results')
    args=p.parse_args()
    if args.jobs<1:p.error('--jobs must be positive')
    if platform.system()!='Darwin':p.error('this build workflow targets macOS')
    meta=json.loads((ROOT/'native/upstream.json').read_text())
    patch=ROOT/'native/git-apfs.patch'
    if hashlib.sha256(patch.read_bytes()).hexdigest()!=meta['patch_sha256']:
        p.error('patch digest differs from native/upstream.json')
    upstream=ROOT/'references/git-core'
    if not upstream.exists():
        upstream.parent.mkdir(parents=True,exist_ok=True)
        run(['git','clone','--depth','1','--branch',meta['tag'],meta['repository'],upstream])
    if subprocess.run(['git','-C',str(upstream),'cat-file','-e',meta['commit']+'^{commit}'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode:
        run(['git','-C',str(upstream),'fetch','--depth=1','--no-tags','origin','tag',meta['tag']])
    commit=subprocess.check_output(['git','-C',str(upstream),'rev-parse',meta['commit']+'^{commit}'],text=True).strip()
    if commit!=meta['commit']:p.error('upstream revision mismatch')
    archive=subprocess.check_output(['git','-C',str(upstream),'archive',commit])
    args.output.mkdir(parents=True,exist_ok=True)
    build=Path(tempfile.mkdtemp(prefix='native-build-',dir=args.output.resolve()))
    print(f'Build directory: {build}',flush=True)
    manifest={'upstream':meta,'platform':platform.platform(),'builds':[]}
    for variant,version in [('git-baseline',meta['version']),('git-apfs',meta['apfs_version'])]:
        source=build/variant;source.mkdir()
        with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
            for member in tar.getmembers():
                destination=(source/member.name).resolve()
                if os.path.commonpath([str(source),str(destination)])!=str(source):
                    raise RuntimeError('archive path escapes build directory')
                if member.issym() or member.islnk():
                    link=(destination.parent/member.linkname if member.issym() else source/member.linkname).resolve()
                    if os.path.commonpath([str(source),str(link)])!=str(source):
                        raise RuntimeError('archive link escapes build directory')
                elif not member.isfile() and not member.isdir():
                    raise RuntimeError('unsupported archive entry')
                tar.extract(member,source)
        env=os.environ.copy()
        env.update(GIT_VERSION=version,GIT_BUILT_FROM_COMMIT=commit,LC_ALL='C',LANG='C')
        # Work on exported sources without discovering the enclosing project repo.
        env['GIT_CEILING_DIRECTORIES']=str(build)
        if variant=='git-apfs':
            run(['git','apply','--check',patch],source,env)
            run(['git','apply',patch],source,env)
        prefix=args.output.resolve()/variant
        command=['make',f'-j{args.jobs}',*meta['make_options'],f'prefix={prefix}','install']
        log=build/(variant+'.log')
        with log.open('wb') as f:
            subprocess.run(command,cwd=source,env=env,stdout=f,stderr=subprocess.STDOUT,check=True)
        binary=prefix/'bin/git'
        manifest['builds'].append({'variant':variant,'binary':str(binary),'sha256':hashlib.sha256(binary.read_bytes()).hexdigest(),'source':str(source),'log':str(log),'command':command})
        (build/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
        print(subprocess.check_output([str(binary),'--version'],text=True).strip(),flush=True)
    print(f'Build manifest: {build}/manifest.json')

if __name__=='__main__':main()
