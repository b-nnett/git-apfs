#!/bin/sh

test_description='APFS verified checkout and bounded clone batches'
. ./test-lib.sh

test_lazy_prereq APFS_CLONE '
	(
		git init -q clone-probe &&
		cd clone-probe &&
		echo probe >file &&
		git add file &&
		git commit -qm probe &&
		GIT_APFS_CLONE_CHECKOUT=1 GIT_APFS_TRACE=1 \
			git worktree add --detach ../clone-target HEAD 2>../clone-probe.log &&
		test_grep "cloned=[1-9]" ../clone-probe.log
	)
'

test_expect_success APFS_CLONE 'setup a registered donor and target' '
	for i in $(test_seq 1 150)
	do
		echo "original $i" >file-$i || return 1
	done &&
	echo original >unrelated &&
	git add file-* unrelated &&
	git commit -m base &&
	git worktree add --detach target HEAD
'

test_expect_success APFS_CLONE 'path restore preserves staging and untracked files' '
	echo dirty >target/file-1 &&
	echo staged >target/unrelated &&
	git -C target add unrelated &&
	echo untracked >target/note &&
	git -C target ls-files --stage -z >expect-index &&
	GIT_APFS_TRACE=1 git -C target restore -- file-1 2>trace &&
	test_grep "cloned=1 " trace &&
	test_cmp file-1 target/file-1 &&
	git -C target ls-files --stage -z >actual-index &&
	test_cmp expect-index actual-index &&
	echo staged >expect-staged &&
	echo untracked >expect-note &&
	test_cmp expect-staged target/unrelated &&
	test_cmp expect-note target/note
'

test_expect_success APFS_CLONE 'dirty donor bytes are rejected' '
	cp file-2 expected &&
	echo wrong-donor >file-2 &&
	echo wrong-target >target/file-2 &&
	GIT_APFS_TRACE=1 git -C target restore -- file-2 2>trace &&
	test_grep "cloned=0 " trace &&
	test_cmp expected target/file-2 &&
	git restore -- file-2
'

test_expect_success APFS_CLONE 'same-sized blob replacements retain native semantics' '
	oid=$(git rev-parse HEAD:file-3) &&
	echo "replaced 3" >replacement &&
	replacement=$(git hash-object -w replacement) &&
	git replace "$oid" "$replacement" &&
	echo dirty >target/file-3 &&
	git -C target restore -- file-3 &&
	test_cmp replacement target/file-3 &&
	git replace -d "$oid"
'

test_expect_success APFS_CLONE 'large restore uses bounded native clone batches' '
	for i in $(test_seq 1 150)
	do
		echo dirty >target/file-$i || return 1
	done &&
	GIT_APFS_TRACE=1 git -C target restore -- "file-*" 2>trace &&
	test_grep "cloned=150 " trace &&
	test_grep "git-apfs-batch:" trace &&
	git -C target diff --exit-code -- "file-*"
'

test_expect_success APFS_CLONE 'batch rejects dirty donors without changing them' '
	for i in $(test_seq 1 150)
	do
		echo "modified $i" >file-$i &&
		echo dirty >target/file-$i || return 1
	done &&
	git diff --binary -- "file-*" >donor-before &&
	GIT_APFS_TRACE=1 git -C target restore -- "file-*" 2>trace &&
	test_grep "cloned=0 " trace &&
	test_grep "git-apfs-batch:" trace &&
	git -C target diff --exit-code -- "file-*" &&
	git diff --binary -- "file-*" >donor-after &&
	test_cmp donor-before donor-after &&
	git restore -- "file-*"
'

test_expect_success APFS_CLONE 'explicit serial setting overrides automatic batches' '
	for i in $(test_seq 1 150)
	do
		echo dirty >target/file-$i || return 1
	done &&
	GIT_APFS_TRACE=1 git -C target -c checkout.workers=1 restore -- "file-*" 2>trace &&
	test_grep "cloned=150 " trace &&
	test_grep ! "git-apfs-batch:" trace &&
	git -C target diff --exit-code -- "file-*"
'

test_expect_success APFS_CLONE 'disabled feature uses ordinary writes' '
	echo dirty >target/file-1 &&
	GIT_APFS_CLONE_CHECKOUT=0 GIT_APFS_TRACE=1 \
		git -C target restore -- file-1 2>trace &&
	test_grep ! "cloned=[1-9]" trace &&
	test_cmp file-1 target/file-1
'

test_done
