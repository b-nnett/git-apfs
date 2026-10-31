/* Git-owned optional donor cache and crash-safe auxiliary-worker leases. GPLv2. */
/* Cache filenames are ASCII OIDs; fdopendir needs the raw dirent API. */
#define PRECOMPOSE_UNICODE_C
#include "git-compat-util.h"
#include "apfs-cache.h"
#include "config.h"
#include "hex.h"
#include "repository.h"
#include "hash.h"
#include "object-file.h"
#ifdef __APPLE__
#include <sys/clonefile.h>
#include <sys/file.h>

struct cached_entry { char *name; uintmax_t charge; struct timespec age; dev_t dev; ino_t ino; };
static struct apfs_cache_stats stats;
static struct cached_entry *entries;
static size_t nr, alloc, victim;
static int root_fd = -1, cache_fd = -1, writer_fd = -1, initialized;
static int leases[64], lease_nr;
static const struct git_hash_algo *hash_algo;
static int evict_one(void);

static int private_dir(int parent, const char *name, int create)
{
	struct stat st;
	int fd;
	if (create && mkdirat(parent, name, 0700) && errno != EEXIST)
		return -1;
	fd = openat(parent, name, O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
	if (fd >= 0 && (fstat(fd, &st) || st.st_uid != geteuid() || (st.st_mode & 0077))) {
		close(fd);
		return -1;
	}
	return fd;
}

static uintmax_t charge(const struct stat *st)
{
	uintmax_t bytes = (uintmax_t)st->st_blocks * 512;
	return bytes < 4096 ? 4096 : bytes;
}

static int valid_name(const char *name)
{
	size_t n = strlen(name), i;
	if (n != 40 && n != 64)
		return 0;
	for (i = 0; i < n; i++)
		if (!((name[i] >= '0' && name[i] <= '9') || (name[i] >= 'a' && name[i] <= 'f')))
			return 0;
	return 1;
}

static int by_age(const void *va, const void *vb)
{
	const struct cached_entry *a = va, *b = vb;
	if (a->age.tv_sec != b->age.tv_sec)
		return a->age.tv_sec < b->age.tv_sec ? -1 : 1;
	if (a->age.tv_nsec != b->age.tv_nsec)
		return a->age.tv_nsec < b->age.tv_nsec ? -1 : 1;
	return strcmp(a->name, b->name);
}

static void scan(int clean)
{
	DIR *dir;
	struct dirent *de;
	struct stat st;
	size_t i;
	for (i = 0; i < nr; i++) free(entries[i].name);
	nr = victim = 0;
	stats.charged_bytes = stats.entries = stats.directory_bytes = 0;
	if (cache_fd < 0) return;
	if (!fstat(cache_fd, &st)) stats.directory_bytes = (uintmax_t)st.st_blocks * 512;
	/* openat gives an independent directory offset; dup would share offsets. */
	dir = fdopendir(openat(cache_fd, ".", O_RDONLY | O_DIRECTORY | O_CLOEXEC));
	if (!dir) return;
	while ((de = readdir(dir))) {
		if (fstatat(cache_fd, de->d_name, &st, AT_SYMLINK_NOFOLLOW) ||
		    !S_ISREG(st.st_mode) || st.st_uid != geteuid()) continue;
		if (clean && !strncmp(de->d_name, ".tmp-", 5)) {
			unlinkat(cache_fd, de->d_name, 0);
			continue;
		}
		if (!valid_name(de->d_name)) continue;
		ALLOC_GROW(entries, nr + 1, alloc);
		entries[nr].name = xstrdup(de->d_name);
		entries[nr].charge = charge(&st);
		entries[nr].age = st.st_mtimespec;
		entries[nr].dev = st.st_dev;
		entries[nr].ino = st.st_ino;
		stats.charged_bytes += entries[nr++].charge;
	}
	closedir(dir);
	stats.entries = nr;
	QSORT(entries, nr, by_age);
}

static void cleanup(void)
{
	size_t i;
	if (writer_fd >= 0) close(writer_fd);
	if (cache_fd >= 0) close(cache_fd);
	if (root_fd >= 0) close(root_fd);
	for (i = 0; i < nr; i++) free(entries[i].name);
	free(entries);
	apfs_budget_release();
}

void apfs_cache_init(struct repository *repo)
{
	unsigned long limit = 0;
	int parent;
	if (initialized) return;
	initialized = 1;
	atexit(cleanup);
	repo_config_get_ulong(repo, "apfs.cachelimit", &limit);
	stats.limit = limit;
	hash_algo = repo->hash_algo;
	root_fd = open(repo_get_common_dir(repo), O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
	if (root_fd < 0) return;
	parent = private_dir(root_fd, "apfs-cache", limit != 0);
	if (parent < 0) return;
	cache_fd = private_dir(parent, "v1", limit != 0);
	close(parent);
	stats.available = cache_fd >= 0;
}

static int begin_write(void)
{
	struct stat st;
	int fd;
	if (!stats.limit || cache_fd < 0 || stats.writer_busy) return 0;
	if (writer_fd >= 0) return 1;
	fd = openat(cache_fd, ".lock", O_RDWR | O_CREAT | O_NOFOLLOW | O_CLOEXEC, 0600);
	if (fd < 0) return 0;
	if (fstat(fd, &st) || !S_ISREG(st.st_mode) || st.st_uid != geteuid() || st.st_nlink != 1 ||
	    flock(fd, LOCK_EX | LOCK_NB)) {
		close(fd);
		stats.writer_busy = 1;
		return 0;
	}
	writer_fd = fd;
	scan(1);
	while (stats.charged_bytes > stats.limit && evict_one());
	return 1;
}

static int evict_one(void)
{
	while (victim < nr) {
		struct cached_entry *e = &entries[victim++];
		struct stat st;
		if (!fstatat(cache_fd, e->name, &st, AT_SYMLINK_NOFOLLOW) &&
		    st.st_dev == e->dev && st.st_ino == e->ino &&
		    !unlinkat(cache_fd, e->name, 0)) {
			stats.charged_bytes -= e->charge;
			stats.entries--;
			stats.evicted++;
			return 1;
		}
	}
	return 0;
}

int apfs_cache_open(const struct object_id *oid)
{
	struct stat st;
	int fd;
	char name[GIT_MAX_HEXSZ + 1];
	if (!stats.limit || cache_fd < 0) return -1;
	oid_to_hex_r(name, oid);
	fd = openat(cache_fd, name, O_RDONLY | O_NOFOLLOW | O_NONBLOCK | O_CLOEXEC);
	if (fd >= 0 && (fstat(fd, &st) || !S_ISREG(st.st_mode) || st.st_uid != geteuid())) {
		close(fd);
		return -1;
	}
	return fd;
}

static int verified_snapshot(int fd, size_t size, const struct object_id *expected)
{
	struct git_hash_ctx ctx;
	struct object_id actual;
	char header[32], buffer[65536];
	size_t done = 0;
	int len = format_object_header(header, sizeof(header), OBJ_BLOB, size);
	git_hash_init(&ctx, hash_algo);
	git_hash_update(&ctx, header, len);
	while (done < size) {
		size_t want = size - done;
		if (want > sizeof(buffer)) want = sizeof(buffer);
		if (read_in_full(fd, buffer, want) != (ssize_t)want) { git_hash_discard(&ctx); return 0; }
		git_hash_update(&ctx, buffer, want);
		done += want;
	}
	git_hash_final_oid(&actual, &ctx);
	return oideq(&actual, expected);
}

int apfs_cache_store(const struct object_id *oid, int source)
{
	struct stat st, clone_st, after;
	uint64_t nonce;
	uintmax_t cost;
	char name[GIT_MAX_HEXSZ + 1], temporary[64];
	int output, result = 0;
	if (!begin_write() || fstat(source, &st)) return 0;
	xsnprintf(name, sizeof(name), "%s", oid_to_hex(oid));
	if (!fstatat(cache_fd, name, &after, AT_SYMLINK_NOFOLLOW)) {
		int existing;
		if (!S_ISREG(after.st_mode) || after.st_uid != geteuid()) return 0;
		existing = openat(cache_fd, name, O_RDONLY | O_NOFOLLOW | O_CLOEXEC);
		if (existing < 0) return 0;
		result = after.st_size > 0 && after.st_size <= 64 * 1024 * 1024 &&
			verified_snapshot(existing, after.st_size, oid);
		close(existing);
		if (result) return 0;
		if (unlinkat(cache_fd, name, 0)) return 0;
		scan(1);
		result = 0;
	}
	cost = charge(&st);
	if (cost > stats.limit) return 0;
	if (csprng_bytes(&nonce, sizeof(nonce), 0) < 0) return 0;
	xsnprintf(temporary, sizeof(temporary), ".tmp-%"PRIx64, nonce);
	if (fclonefileat(source, cache_fd, temporary, CLONE_NOOWNERCOPY)) return 0;
	output = openat(cache_fd, temporary, O_RDONLY | O_NOFOLLOW | O_CLOEXEC);
	if (output < 0) goto out;
	if (fstat(output, &clone_st) || fstat(source, &after) ||
	    st.st_ino != after.st_ino || st.st_size != after.st_size ||
	    st.st_mtimespec.tv_sec != after.st_mtimespec.tv_sec ||
	    st.st_mtimespec.tv_nsec != after.st_mtimespec.tv_nsec ||
	    st.st_ctimespec.tv_sec != after.st_ctimespec.tv_sec ||
	    st.st_ctimespec.tv_nsec != after.st_ctimespec.tv_nsec ||
	    !verified_snapshot(output, clone_st.st_size, oid) || fchmod(output, 0400) || futimens(output, NULL)) goto close_out;
	cost = charge(&clone_st);
	while (cost <= stats.limit && stats.charged_bytes > stats.limit - cost)
		if (!evict_one()) break;
	if (cost > stats.limit || stats.charged_bytes > stats.limit - cost) goto close_out;
	if (!renameatx_np(cache_fd, temporary, cache_fd, name, RENAME_EXCL)) {
		stats.charged_bytes += cost;
		stats.entries++;
		stats.stored++;
		result = 1;
		/* New entries join FIFO eviction order without a directory rescan. */
		ALLOC_GROW(entries, nr + 1, alloc);
		entries[nr].name = xstrdup(name);
		entries[nr].charge = cost;
		entries[nr].dev = clone_st.st_dev;
		entries[nr].ino = clone_st.st_ino;
		entries[nr++].age = clone_st.st_mtimespec;
	}
 close_out:
	close(output);
 out:
	if (!result) unlinkat(cache_fd, temporary, 0);
	return result;
}

int apfs_cache_prune(void)
{
	uintmax_t saved = stats.limit;
	int ok;
	if (!stats.limit) stats.limit = UINTMAX_MAX;
	ok = begin_write();
	stats.limit = saved;
	if (!ok) return -1;
	while (evict_one());
	return stats.entries ? -1 : 0;
}

void apfs_cache_stats(struct apfs_cache_stats *out, int refresh)
{
	if (refresh) scan(0);
	*out = stats;
}

int apfs_budget_acquire(struct repository *repo, int wanted, int budget)
{
	int parent, i;
	struct stat st;
	if (lease_nr) return lease_nr;
	if (wanted < 1 || budget < 1) return 0;
	if (budget > 64) budget = 64;
	apfs_cache_init(repo);
	if (root_fd < 0) return 0;
	parent = private_dir(root_fd, "apfs-worker-budget", 1);
	if (parent < 0) return 0;
	for (i = 0; i < budget && lease_nr < wanted; i++) {
		char name[32];
		int fd;
		xsnprintf(name, sizeof(name), "slot-%d", i);
		fd = openat(parent, name, O_RDWR | O_CREAT | O_NOFOLLOW | O_CLOEXEC, 0600);
		if (fd < 0) continue;
		if (fstat(fd, &st) || !S_ISREG(st.st_mode) || st.st_uid != geteuid() || st.st_nlink != 1 ||
		    flock(fd, LOCK_EX | LOCK_NB)) { close(fd); continue; }
		leases[lease_nr++] = fd;
	}
	close(parent);
	return lease_nr;
}

void apfs_budget_release(void)
{
	while (lease_nr) close(leases[--lease_nr]);
}
#else
void apfs_cache_init(struct repository *r UNUSED) { }
int apfs_cache_open(const struct object_id *oid UNUSED) { return -1; }
int apfs_cache_store(const struct object_id *oid UNUSED, int source UNUSED) { return 0; }
int apfs_cache_prune(void) { return -1; }
void apfs_cache_stats(struct apfs_cache_stats *out, int refresh UNUSED) { memset(out, 0, sizeof(*out)); }
int apfs_budget_acquire(struct repository *r UNUSED, int wanted UNUSED, int budget UNUSED) { return 0; }
void apfs_budget_release(void) { }
#endif
