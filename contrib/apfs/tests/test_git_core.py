"""Differential tests for the actual Git binaries, not a command wrapper."""
import hashlib
import os
from pathlib import Path
import re
import resource
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).parents[1]/'benchmarks'))
import bench

ROOT=Path(__file__).parents[1]
BASE=Path(os.environ.get('GIT_APFS_BASELINE',ROOT/'benchmark-results/git-baseline/bin/git')).resolve()
FORK=Path(os.environ.get('GIT_APFS_BINARY',ROOT/'benchmark-results/git-apfs/bin/git')).resolve()

@unittest.skipUnless(BASE.is_file() and FORK.is_file(),'build the native Git baseline and Git APFS first')
class GitCoreTests(unittest.TestCase):
    def fixture(self,root,files=20):
        env=bench.environment(root)
        env['PATH']=str(BASE.parent)+os.pathsep+env['PATH']
        env['LC_ALL']='C'
        repo,base,changed=bench.fixture(root,env,files,file_bytes=128)
        return env,repo,base,changed

    def run_git(self,binary,repo,env,*args,umask=None,nofile=None):
        local=env.copy();local['GIT_APFS_TRACE']='1'
        local['PATH']=str(binary.parent)+os.pathsep+env['PATH']
        kw={} if umask is None else {'umask':umask}
        if nofile:
            hard=resource.getrlimit(resource.RLIMIT_NOFILE)[1]
            kw['preexec_fn']=lambda: resource.setrlimit(resource.RLIMIT_NOFILE,(nofile,hard))
        return subprocess.run([str(binary),*args],cwd=repo,env=local,stdout=subprocess.PIPE,stderr=subprocess.PIPE,**kw)

    def worktree(self,repo,env,path,ref):
        bench.git(repo,env,'worktree','add','--detach',str(path),ref)

    def test_binary_is_git_with_normal_builtins(self):
        out=subprocess.check_output([FORK,'--list-cmds=builtins'],text=True)
        self.assertTrue({'commit','switch','restore','fetch','push','status','worktree'}<=set(out.splitlines()))
        self.assertIn('.apfs.',subprocess.check_output([FORK,'--version'],text=True))

    def test_switch_matches_native_and_clones_only_real_bytes(self):
        outcomes=[]
        for binary in (BASE,FORK):
            with tempfile.TemporaryDirectory() as d:
                root=Path(d);env,repo,base,changed=self.fixture(root)
                target=root/'target';self.worktree(repo,env,target,changed)
                source=bench.snapshot(repo)
                result=self.run_git(binary,target,env,'switch','--detach',base)
                self.assertEqual(0,result.returncode,result.stderr)
                self.assertEqual(base,bench.git(target,env,'rev-parse','HEAD'))
                self.assertEqual('',bench.git(target,env,'status','--porcelain','-z'))
                self.assertEqual(source,bench.snapshot(repo))
                outcomes.append(bench.tracked_snapshot(target,env))
                if binary==FORK:self.assertRegex(result.stderr,rb'cloned=[1-9]')
        self.assertEqual(*outcomes)

    def test_restore_paths_preserves_unrelated_staged_and_untracked_work(self):
        for binary in (BASE,FORK):
            with self.subTest(binary=binary),tempfile.TemporaryDirectory() as d:
                root=Path(d);env,repo,base,_=self.fixture(root)
                target=root/'target';self.worktree(repo,env,target,base)
                p='packages/pkg00/src/file000000.txt'
                (target/p).write_bytes(b'dirty')
                other='space and café.txt';(target/other).write_text('keep staged\n')
                bench.git(target,env,'add','--',other)
                (target/'untracked').write_text('keep untracked\n')
                before_index=bench.git(target,env,'ls-files','--stage','-z')
                before=(target/other).stat()
                result=self.run_git(binary,target/'packages',env,'restore','--','pkg00/src/file000000.txt')
                self.assertEqual(0,result.returncode,result.stderr)
                self.assertEqual((repo/p).read_bytes(),(target/p).read_bytes())
                self.assertEqual(before_index,bench.git(target,env,'ls-files','--stage','-z'))
                self.assertEqual(before.st_ino,(target/other).stat().st_ino)
                self.assertEqual('keep staged\n',(target/other).read_text())
                self.assertEqual('keep untracked\n',(target/'untracked').read_text())
                if binary==FORK:self.assertIn(b'cloned=1 ',result.stderr)

    def test_staged_only_restore_does_not_touch_working_files(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);env,repo,base,_=self.fixture(root)
            target=root/'target';self.worktree(repo,env,target,base)
            p=target/'space and café.txt';p.write_text('staged\n');bench.git(target,env,'add','--',p.name)
            before=p.stat();result=self.run_git(FORK,target,env,'restore','--staged','--',p.name)
            self.assertEqual(0,result.returncode,result.stderr)
            self.assertEqual('staged\n',p.read_text());self.assertEqual(before,p.stat())
            self.assertEqual('',bench.git(target,env,'diff','--cached','--name-only'))
            self.assertNotRegex(result.stderr,rb'cloned=[1-9]')

    def test_dirty_donor_cannot_supply_wrong_bytes(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);env,repo,base,_=self.fixture(root)
            target=root/'target';self.worktree(repo,env,target,base)
            p='space and café.txt';expected=(repo/p).read_bytes()
            source_stat=(repo/p).stat();(repo/p).write_bytes(b'x'*len(expected))
            os.utime(repo/p,ns=(source_stat.st_atime_ns,source_stat.st_mtime_ns))
            (target/p).write_text('dirty target')
            result=self.run_git(FORK,target,env,'restore','--',p)
            self.assertEqual(0,result.returncode,result.stderr)
            self.assertEqual(expected,(target/p).read_bytes())
            self.assertIn(b'cloned=0 ',result.stderr)

    def test_restore_from_other_commit_keeps_head_and_index(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);env,repo,base,changed=self.fixture(root)
            donor=root/'donor';self.worktree(repo,env,donor,changed)
            target=root/'target';self.worktree(repo,env,target,base)
            p='packages/pkg00/src/file000000.txt';index=bench.git(target,env,'ls-files','--stage','-z')
            result=self.run_git(FORK,target,env,'restore','--source='+changed,'--worktree','--',p)
            self.assertEqual(0,result.returncode,result.stderr)
            self.assertEqual(base,bench.git(target,env,'rev-parse','HEAD'))
            self.assertEqual(index,bench.git(target,env,'ls-files','--stage','-z'))
            self.assertEqual((donor/p).read_bytes(),(target/p).read_bytes())
            self.assertIn(b'cloned=1 ',result.stderr)

    def test_failed_switch_does_not_overwrite_dirty_work(self):
        for binary in (BASE,FORK):
            with tempfile.TemporaryDirectory() as d:
                root=Path(d);env,repo,base,changed=self.fixture(root)
                target=root/'target';self.worktree(repo,env,target,base)
                p=target/'packages/pkg00/src/file000000.txt';p.write_text('protect dirty work\n')
                result=self.run_git(binary,target,env,'switch','--detach',changed)
                self.assertNotEqual(0,result.returncode)
                self.assertEqual('protect dirty work\n',p.read_text())
                self.assertEqual(base,bench.git(target,env,'rev-parse','HEAD'))

    def test_carried_dirty_work_keeps_bytes_and_inode(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);env,repo,base,changed=self.fixture(root)
            target=root/'target';self.worktree(repo,env,target,changed)
            p=target/'space and café.txt';p.write_text('carry dirty work\n');before=p.stat()
            result=self.run_git(FORK,target,env,'switch','--detach',base)
            self.assertEqual(0,result.returncode,result.stderr)
            self.assertEqual('carry dirty work\n',p.read_text());self.assertEqual(before.st_ino,p.stat().st_ino)

    def test_filters_and_hooks_retain_native_behavior(self):
        for binary in (BASE,FORK):
            with tempfile.TemporaryDirectory() as d:
                root=Path(d);env,repo,base,changed=self.fixture(root)
                target=root/'target';self.worktree(repo,env,target,base)
                bench.git(repo,env,'config','filter.upper.clean','tr A-Z a-z')
                bench.git(repo,env,'config','filter.upper.smudge','tr a-z A-Z')
                (target/'.gitattributes').write_text('*.txt filter=upper\n')
                bench.git(target,env,'add','.gitattributes');bench.git(target,env,'commit','-qm','attributes')
                p=target/'space and café.txt';p.write_text('dirty')
                result=self.run_git(binary,target,env,'restore','--',p.name)
                self.assertEqual(0,result.returncode,result.stderr)
                self.assertEqual('UNUSUAL NAME\n',p.read_text())
                hooks=root/'hooks';hooks.mkdir();log=root/'events'
                (hooks/'post-checkout').write_text('#!/bin/sh\nprintf "hook\\n" >> "'+str(log)+'"\n')
                (hooks/'post-checkout').chmod(0o755)
                bench.git(repo,env,'config','core.hooksPath',str(hooks))
                result=self.run_git(binary,target,env,'switch','--detach',changed)
                self.assertEqual(0,result.returncode,result.stderr)
                self.assertEqual('hook\n',log.read_text())

    def test_symlinks_modes_binary_data_and_unusual_names(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);env,repo,_,_=self.fixture(root)
            binary_data=bytes(range(256))*16
            (repo/'binary').write_bytes(binary_data)
            bench.git(repo,env,'add','binary');bench.git(repo,env,'commit','-qm','binary')
            target=root/'target';self.worktree(repo,env,target,'HEAD')
            for p in ['binary','run.sh','line\nbreak.txt']:(target/p).write_bytes(b'changed')
            (target/'link').unlink();(target/'link').symlink_to('wrong')
            result=self.run_git(FORK,target,env,'restore','--','binary','run.sh','line\nbreak.txt','link',umask=0o077)
            self.assertEqual(0,result.returncode,result.stderr)
            self.assertEqual(binary_data,(target/'binary').read_bytes())
            self.assertEqual(0o600,(target/'binary').stat().st_mode&0o777)
            self.assertEqual(0o700,(target/'run.sh').stat().st_mode&0o777)
            self.assertEqual('space and café.txt',os.readlink(target/'link'))
            self.assertEqual((repo/'line\nbreak.txt').read_bytes(),(target/'line\nbreak.txt').read_bytes())

    def test_index_and_edit_detection_after_clone(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);env,repo,base,_=self.fixture(root)
            target=root/'target';self.worktree(repo,env,target,base)
            p=target/'space and café.txt';p.write_text('dirty')
            result=self.run_git(FORK,target,env,'restore','--',p.name)
            self.assertEqual(0,result.returncode,result.stderr)
            self.assertEqual('',bench.git(target,env,'status','--porcelain','-z'))
            old=p.stat();data=p.read_bytes();p.write_bytes(bytes([data[0]^1])+data[1:]);os.utime(p,ns=(old.st_atime_ns,old.st_mtime_ns))
            self.assertIn(p.name,bench.git(target,env,'status','--porcelain','-z'))

    def test_parallel_checkout_clones_and_feature_can_be_disabled(self):
        for enabled in ('1','0'):
            with tempfile.TemporaryDirectory() as d:
                root=Path(d);env,repo,base,changed=self.fixture(root,200)
                target=root/'target';self.worktree(repo,env,target,changed)
                bench.git(repo,env,'config','checkout.workers','2')
                bench.git(repo,env,'config','checkout.thresholdForParallelism','1')
                env['GIT_APFS_CLONE_CHECKOUT']=enabled
                result=self.run_git(FORK,target,env,'switch','--detach',base)
                self.assertEqual(0,result.returncode,result.stderr)
                self.assertEqual(bench.tracked_snapshot(repo,env),bench.tracked_snapshot(target,env))
                if enabled=='1':self.assertRegex(result.stderr,rb'cloned=[1-9]')
                else:self.assertNotRegex(result.stderr,rb'cloned=[1-9]')

    def test_matching_dirty_donor_bytes_do_not_require_matching_head(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);env,repo,base,changed=self.fixture(root)
            target=root/'target';self.worktree(repo,env,target,base)
            relative='packages/pkg00/src/file000000.txt'
            expected=(repo/relative).read_bytes()
            bench.git(repo,env,'switch','--detach',changed)
            (repo/relative).write_bytes(expected)
            donor_before=bench.snapshot(repo)
            (target/relative).write_bytes(b'dirty target')
            result=self.run_git(FORK,target,env,'restore','--',relative)
            self.assertEqual(0,result.returncode,result.stderr)
            self.assertEqual(expected,(target/relative).read_bytes())
            self.assertIn(b'cloned=1 ',result.stderr)
            self.assertEqual(donor_before,bench.snapshot(repo))

    def test_automatic_parallelism_and_explicit_serial_override(self):
        for workers in (None,'1'):
            with self.subTest(workers=workers),tempfile.TemporaryDirectory() as d:
                root=Path(d);env,repo,base,changed=self.fixture(root,1200)
                target=root/'target';self.worktree(repo,env,target,changed)
                if workers:bench.git(repo,env,'config','checkout.workers',workers)
                result=self.run_git(FORK,target,env,'switch','--detach',base)
                self.assertEqual(0,result.returncode,result.stderr)
                counts=re.findall(rb'git-apfs: attempted=(\d+) cloned=(\d+)',result.stderr)
                self.assertEqual(bench.tracked_snapshot(repo,env),bench.tracked_snapshot(target,env))
                self.assertGreaterEqual(sum(int(c[1]) for c in counts),120)
                if workers:self.assertEqual(1,len(counts))
                elif (os.cpu_count() or 1)>1:self.assertIn(b'git-apfs-batch:',result.stderr)

    def test_clone_batches_bound_open_descriptors(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);env,repo,base,changed=self.fixture(root,1200)
            target=root/'target';self.worktree(repo,env,target,changed)
            result=self.run_git(FORK,target,env,'switch','--detach',base,nofile=96)
            self.assertEqual(0,result.returncode,result.stderr)
            self.assertIn(b'git-apfs-batch:',result.stderr)
            self.assertNotIn(b'Too many open files',result.stderr)
            self.assertGreaterEqual(sum(int(n) for n in re.findall(rb'cloned=(\d+)',result.stderr)),120)
            self.assertEqual(bench.tracked_snapshot(repo,env),bench.tracked_snapshot(target,env))

    def test_same_sized_replacement_blob_matches_native(self):
        for binary in (BASE,FORK):
            with self.subTest(binary=binary),tempfile.TemporaryDirectory() as d:
                root=Path(d);env,repo,base,_=self.fixture(root)
                relative='packages/pkg00/src/file000000.txt'
                original=(repo/relative).read_bytes()
                oid=bench.git(repo,env,'rev-parse','HEAD:'+relative)
                replacement=b'R'*len(original)
                replacement_oid=subprocess.check_output([str(BASE),'hash-object','-w','--stdin'],cwd=repo,env=env,input=replacement).decode().strip()
                target=root/'target';self.worktree(repo,env,target,base)
                bench.git(repo,env,'replace',oid,replacement_oid)
                (target/relative).write_bytes(b'dirty')
                result=self.run_git(binary,target,env,'restore','--',relative)
                self.assertEqual(0,result.returncode,result.stderr)
                self.assertEqual(replacement,(target/relative).read_bytes())
                self.assertEqual(original,(repo/relative).read_bytes())
                if binary==FORK:
                    (repo/relative).write_bytes(replacement)
                    (target/relative).write_bytes(b'dirty again')
                    result=self.run_git(binary,target,env,'restore','--',relative)
                    self.assertEqual(0,result.returncode,result.stderr)
                    self.assertEqual(replacement,(target/relative).read_bytes())
                    self.assertIn(b'cloned=1 ',result.stderr)

    def test_parallel_batch_rejects_same_sized_dirty_donors(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);env,repo,base,changed=self.fixture(root,1200)
            wanted=bench.tracked_snapshot(repo,env)
            target=root/'target';self.worktree(repo,env,target,changed)
            paths=sorted(repo.glob('packages/*/src/*.txt'))[:120]
            for path in paths:
                before=path.stat()
                path.write_bytes(b'X'*before.st_size)
                os.utime(path,ns=(before.st_atime_ns,before.st_mtime_ns))
            source_before=bench.snapshot(repo)
            result=self.run_git(FORK,target,env,'switch','--detach',base)
            self.assertEqual(0,result.returncode,result.stderr)
            self.assertIn(b'git-apfs-batch:',result.stderr)
            self.assertLessEqual(sum(int(n) for n in re.findall(rb'cloned=(\d+)',result.stderr)),1)
            self.assertEqual(wanted,bench.tracked_snapshot(target,env))
            self.assertEqual(source_before,bench.snapshot(repo))
            self.assertFalse(list(target.rglob('.git-apfs-*')))

    def test_sha256_checkout_uses_the_same_native_engine(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);env=bench.environment(root);env['PATH']=str(BASE.parent)+os.pathsep+env['PATH']
            repo=root/'repo';repo.mkdir();bench.git(repo,env,'init','-q','--object-format=sha256','-b','main')
            (repo/'file').write_bytes(b'original bytes\n');bench.git(repo,env,'add','.');bench.git(repo,env,'commit','-qm','sha256 base')
            target=root/'target';self.worktree(repo,env,target,'HEAD');(target/'file').write_bytes(b'dirty')
            result=self.run_git(FORK,target,env,'restore','--','file')
            self.assertEqual(0,result.returncode,result.stderr)
            self.assertEqual(b'original bytes\n',(target/'file').read_bytes())
            self.assertIn(b'cloned=1 ',result.stderr)

    def test_source_symlink_ancestor_is_not_followed(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);env,repo,base,_=self.fixture(root)
            target=root/'target';self.worktree(repo,env,target,base)
            relative=Path('packages/pkg00/src/file000000.txt');data=(repo/relative).read_bytes()
            outside=root/'outside';outside.mkdir();(outside/relative.name).write_bytes(data)
            (repo/relative).unlink();(repo/relative.parent).rmdir();(repo/relative.parent).symlink_to(outside)
            (target/relative).write_bytes(b'dirty')
            result=self.run_git(FORK,target,env,'restore','--',str(relative))
            self.assertEqual(0,result.returncode,result.stderr)
            self.assertEqual(data,(target/relative).read_bytes())
            self.assertEqual(data,(outside/relative.name).read_bytes())
            self.assertIn(b'cloned=0 ',result.stderr)

    def test_large_blob_falls_back_even_when_dirty_donor_is_small(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);env,repo,_,_=self.fixture(root)
            size=65*1024*1024
            with (repo/'big').open('wb') as f:f.seek(size-1);f.write(b'\0')
            bench.git(repo,env,'add','big');bench.git(repo,env,'commit','-qm','large blob')
            target=root/'target';self.worktree(repo,env,target,'HEAD')
            (repo/'big').write_bytes(b'x');(target/'big').write_bytes(b'dirty')
            result=self.run_git(FORK,target,env,'restore','--','big')
            self.assertEqual(0,result.returncode,result.stderr)
            self.assertEqual(size,(target/'big').stat().st_size)
            self.assertIn(b'cloned=0 ',result.stderr)

if __name__=='__main__':unittest.main()
