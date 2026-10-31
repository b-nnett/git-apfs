/* APFS checkout engine. Git object/index/config access stays on the caller. GPLv2. */
#define USE_THE_REPOSITORY_VARIABLE
#include "git-compat-util.h"
#include "apfs-checkout.h"
#include "apfs-cache.h"
#include "builtin.h"
#include "config.h"
#include "abspath.h"
#include "convert.h"
#include "entry.h"
#include "hex.h"
#include "odb.h"
#include "object-file.h"
#include "replace-object.h"
#include "parallel-checkout.h"
#include "read-cache-ll.h"
#include "worktree.h"
#include "thread-utils.h"
#include "json-writer.h"
#include "trace.h"
#include "setup.h"
#ifdef __APPLE__
#include <sys/clonefile.h>
#include <sys/xattr.h>
#include <sys/mount.h>
#include <sys/resource.h>

static struct worktree **donors;
static int donor_nr, initialized, enabled, trace_enabled, diagnostic, profiling;
static int batch_fallback, selected_workers, worker_budget = 8;
static int batch_workers, has_sources;
static uintmax_t checkout_entries;
static mode_t checkout_umask;
static uintmax_t attempted, cloned_files, cloned_bytes, batches, cache_hits;
static uint64_t object_ns, verify_ns, clone_ns, publish_ns, batch_ns, donor_probes;
static const char *reason_names[] = { "disabled", "conversion", "file_type", "prefix",
	"object_unavailable", "empty", "size_limit", "no_matching_donor", "donor_missing",
	"donor_metadata", "donor_mismatch", "donor_changed", "clone_error", "publish_error" };
static uint64_t reasons[ARRAY_SIZE(reason_names)];

struct donor_directory {
	int fd;
	const char *root;
	char *path;
	size_t len;
	int preferred;
};
static struct donor_directory main_source_dir = { .fd = -1 };
static void initialize(void);

static uint64_t stamp(void) { return profiling ? getnanotime() : 0; }
static void measure(uint64_t *counter, uint64_t start)
{
	if (profiling) __atomic_fetch_add(counter, getnanotime() - start, __ATOMIC_RELAXED);
}
static void reject(const char *reason)
{
	size_t i;
	if (!diagnostic) return;
	for (i = 0; i < ARRAY_SIZE(reason_names); i++)
		if (!strcmp(reason, reason_names[i])) {
			__atomic_fetch_add(&reasons[i], 1, __ATOMIC_RELAXED);
			return;
		}
}
static void clear_donor_directory(struct donor_directory *cache)
{
	if (cache->fd >= 0) close(cache->fd);
	free(cache->path);
	cache->fd = -1;
	cache->path = NULL;
}

static void write_diagnostics(FILE *out, const char *event)
{
	struct json_writer jw = JSON_WRITER_INIT;
	struct apfs_cache_stats cache;
	size_t i;
	apfs_cache_stats(&cache, 1);
	jw_object_begin(&jw, 0);
	jw_object_string(&jw, "event", event);
	jw_object_intmax(&jw, "schema_version", 1);
	jw_object_bool(&jw, "clone_enabled", enabled);
	jw_object_intmax(&jw, "registered_worktrees", donor_nr);
	jw_object_intmax(&jw, "process_id", getpid());
	jw_object_intmax(&jw, "checkout_entries", checkout_entries);
	jw_object_intmax(&jw, "attempted", attempted);
	jw_object_intmax(&jw, "cloned", cloned_files);
	jw_object_intmax(&jw, "cloned_bytes", cloned_bytes);
	jw_object_intmax(&jw, "donor_probes", donor_probes);
	jw_object_inline_begin_object(&jw, "rejection_events");
	for (i = 0; i < ARRAY_SIZE(reason_names); i++) jw_object_intmax(&jw, reason_names[i], reasons[i]);
	jw_end(&jw);
	jw_object_inline_begin_object(&jw, "workers");
	jw_object_intmax(&jw, "auxiliary_budget", worker_budget);
	jw_object_intmax(&jw, "selected", selected_workers ? selected_workers : 1);
	jw_object_intmax(&jw, "batches", batches);
	jw_object_intmax(&jw, "batch_peak", batch_workers);
	jw_end(&jw);
	jw_object_inline_begin_object(&jw, "cache");
	jw_object_intmax(&jw, "limit_bytes", cache.limit);
	jw_object_bool(&jw, "fsmonitor_stat_guard", enabled || cache.limit != 0);
	jw_object_intmax(&jw, "charged_file_bytes", cache.charged_bytes);
	jw_object_intmax(&jw, "directory_allocated_bytes", cache.directory_bytes);
	jw_object_intmax(&jw, "entries", cache.entries);
	jw_object_intmax(&jw, "stored", cache.stored);
	jw_object_intmax(&jw, "evicted", cache.evicted);
	jw_object_intmax(&jw, "hits", cache_hits);
	jw_object_bool(&jw, "available", cache.available);
	jw_object_bool(&jw, "writer_busy", cache.writer_busy);
	jw_end(&jw);
	jw_object_inline_begin_object(&jw, "work_ns");
	jw_object_intmax(&jw, "object_lookup", object_ns);
	jw_object_intmax(&jw, "donor_verify", verify_ns);
	jw_object_intmax(&jw, "clone", clone_ns);
	jw_object_intmax(&jw, "publication", publish_ns);
	jw_object_intmax(&jw, "batch_wall", batch_ns);
	jw_end(&jw);
	jw_end(&jw);
	fprintf(out, "%s\n", jw.json.buf);
	jw_release(&jw);
}
static void report_clones(void)
{
	if (trace_enabled) fprintf(stderr, "git-apfs: attempted=%"PRIuMAX" cloned=%"PRIuMAX" bytes=%"PRIuMAX"\n", attempted, cloned_files, cloned_bytes);
	if (trace_enabled && batches) fprintf(stderr, "git-apfs-batch: batches=%"PRIuMAX" workers=%d\n", batches, batch_workers);
	if (diagnostic) write_diagnostics(stderr, "git-apfs-checkout");
	clear_donor_directory(&main_source_dir);
	if (donors) free_worktrees(donors);
}
static void initialize(void)
{
	if (initialized) return;
	initialized = 1;
	enabled = 1;
	repo_config_get_bool(the_repository, "apfs.clonecheckout", &enabled);
	enabled = git_env_bool("GIT_APFS_CLONE_CHECKOUT", enabled);
	trace_enabled = git_env_bool("GIT_APFS_TRACE", 0);
	diagnostic = git_env_bool("GIT_APFS_TRACE_JSON", 0);
	profiling = git_env_bool("GIT_APFS_PROFILE", 0);
	diagnostic |= profiling;
	repo_config_get_int(the_repository, "apfs.workerbudget", &worker_budget);
	if (worker_budget < 0 || worker_budget > 64) die("apfs.workerBudget must be between 0 and 64");
	checkout_umask = umask(0);
	umask(checkout_umask);
	apfs_cache_init(the_repository);
	if (enabled) {
		donors = get_worktrees_without_reading_head(the_repository);
		while (donors[donor_nr]) donor_nr++;
	}
	atexit(report_clones);
}

int apfs_checkout_default_workers(void)
{
	struct statfs fs;
	struct stat current, donor;
	struct apfs_cache_stats cache;
	int i, eligible = 0, wanted;
	initialize();

	if (!enabled || statfs(".", &fs) || strcmp(fs.f_fstypename, "apfs") || stat(".", &current)) return 1;
	apfs_cache_stats(&cache, 0);
	eligible = cache.limit && cache.available;
	for (i = 0; !eligible && i < donor_nr; i++)
		if (!donors[i]->is_current && !donors[i]->is_bare &&
		    !lstat(donors[i]->path, &donor) && S_ISDIR(donor.st_mode) && donor.st_dev == current.st_dev) eligible = 1;
	has_sources = eligible;
	if (!eligible || !worker_budget) return 1;
	wanted = online_cpus() < 8 ? online_cpus() : 8;
	return wanted;
}

int apfs_checkout_large_batch(struct parallel_checkout_item *items, size_t nr)
{
	size_t i, bytes = 0, size;
	int explicit_threshold;
	initialize();
	if (nr < 2 || !enabled || !repo_config_get_int(the_repository, "checkout.thresholdForParallelism", &explicit_threshold)) return 0;
	for (i = 0; i < nr; i++) {
		if (convert_attrs_preserve_bytes(&items[i].ca) &&
		    odb_read_object_info(the_repository->objects, &items[i].ce->oid, &size) == OBJ_BLOB && size <= 64 * 1024 * 1024) bytes += size;
		if (bytes >= 8 * 1024 * 1024) return 1;
	}
	return 0;
}
void apfs_checkout_finish_batch(void) { batch_fallback = 0; }

static int unchanged(const struct stat *a, const struct stat *b)
{
	return a->st_dev == b->st_dev && a->st_ino == b->st_ino &&
		a->st_size == b->st_size && a->st_mode == b->st_mode &&
		a->st_uid == b->st_uid && a->st_gid == b->st_gid &&
		a->st_flags == b->st_flags &&
		a->st_mtimespec.tv_sec == b->st_mtimespec.tv_sec &&
		a->st_mtimespec.tv_nsec == b->st_mtimespec.tv_nsec &&
		a->st_ctimespec.tv_sec == b->st_ctimespec.tv_sec &&
		a->st_ctimespec.tv_nsec == b->st_ctimespec.tv_nsec;
}

/* Pin every directory component; never follow a donor/target ancestor link. */
static int parent_fd(const char *root, const char *relative, const char **name)
{
	int fd = open(root, O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
	char *copy, *p, *slash;
	if (fd < 0)
		return -1;
	if (!*relative || is_absolute_path(relative)) {
		close(fd);
		return -1;
	}
	copy = xstrdup(relative);
	p = copy;
	while ((slash = strchr(p, '/'))) {
		int next;
		*slash = '\0';
		if (!*p || !strcmp(p, ".") || !strcmp(p, "..")) {
			close(fd);
			free(copy);
			return -1;
		}
		next = openat(fd, p, O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
		close(fd);
		if (next < 0) {
			free(copy);
			return -1;
		}
		fd = next;
		p = slash + 1;
	}
	free(copy);
	*name = strrchr(relative, '/');
	*name = *name ? *name + 1 : relative;
	if (!**name || !strcmp(*name, ".") || !strcmp(*name, "..")) {
		close(fd);
		return -1;
	}
	return fd;
}

/* Only donor directories are cached. A pinned former donor directory remains
 * safe because every source is byte-verified. Target ancestors are always
 * walked afresh, so writes cannot disappear into a cached detached directory. */
static int donor_parent_fd(struct donor_directory *cache, const char *root,
			   const char *path, const char **name)
{
	const char *slash = strrchr(path, '/');
	size_t len = slash ? slash - path : 0;
	int fd;

	*name = slash ? slash + 1 : path;
	if (cache->fd >= 0 && root == cache->root &&
	    len == cache->len && !strncmp(path, cache->path, len))
		return cache->fd;
	fd = parent_fd(root, path, name);
	if (fd < 0)
		return -1;
	if (cache->fd >= 0)
		close(cache->fd);
	free(cache->path);
	cache->path = xmemdupz(path, len);
	cache->root = root;
	cache->len = len;
	cache->fd = fd;
	return fd;
}

static int matches_blob_oid(int fd, size_t size, const struct object_id *oid,
			    const struct git_hash_algo *algo)
{
	struct git_hash_ctx ctx;
	struct object_id actual;
	char header[32], buffer[65536];
	size_t offset = 0;
	int len = format_object_header(header, sizeof(header), OBJ_BLOB, size);
	git_hash_init(&ctx, algo);
	git_hash_update(&ctx, header, len);
	while (offset < size) {
		size_t wanted = size - offset;
		if (wanted > sizeof(buffer)) wanted = sizeof(buffer);
		if (read_in_full(fd, buffer, wanted) != (ssize_t)wanted) { git_hash_discard(&ctx); return 0; }
		git_hash_update(&ctx, buffer, wanted);
		offset += wanted;
	}
	git_hash_final_oid(&actual, &ctx);
	return oideq(&actual, oid);
}
struct clone_plan {
	const char *path, *name;
	struct object_id expected_oid;
	const struct git_hash_algo *hash_algo;
	int source, parent, from_cache, result, saved_errno;
	struct stat before, st;
	size_t size;
	mode_t mode;
	char temporary[96];
};

static int prepare_plan(const struct cache_entry *ce, const char *path,
			const struct conv_attrs *ca, const struct checkout *state, struct clone_plan *plan)
{
	size_t size;
	uint64_t nonce[2], start;
	initialize();
	checkout_entries++;
	if (!enabled) { reject("disabled"); return 0; }
	if (!S_ISREG(ce->ce_mode)) { reject("file_type"); return 0; }
	if (state->base_dir_len || strcmp(path, ce->name)) { reject("prefix"); return 0; }
	if (!convert_attrs_preserve_bytes(ca)) { reject("conversion"); return 0; }
	attempted++;
	start = stamp();
	if (odb_read_object_info(the_repository->objects, &ce->oid, &size) != OBJ_BLOB) { reject("object_unavailable"); return 0; }
	measure(&object_ns, start);
	if (!size) { reject("empty"); return 0; }
	if (size > 64 * 1024 * 1024) { reject("size_limit"); return 0; }
	if (csprng_bytes(nonce, sizeof(nonce), 0) < 0) return 0;
	memset(plan, 0, sizeof(*plan));
	plan->path = path;
	plan->size = size;
	plan->mode = ((ce->ce_mode & 0100) ? 0777 : 0666) & ~checkout_umask;
	plan->hash_algo = the_repository->hash_algo;
	oidcpy(&plan->expected_oid, lookup_replace_object(the_repository, &ce->oid));
	xsnprintf(plan->temporary, sizeof(plan->temporary), ".git-apfs-%"PRIx64"-%"PRIx64, nonce[0], nonce[1]);
	return 1;
}
static void execute_clone(struct clone_plan *plan)
{
	struct stat created, current, after;
	int output = -1, published = 0, have_created = 0;
	uint64_t started = stamp();

	plan->result = 0;
	if (fclonefileat(plan->source, plan->parent, plan->temporary, CLONE_NOOWNERCOPY)) {
		reject("clone_error");
		goto out;
	}
	measure(&clone_ns, started);
	started = stamp();
	have_created = !fstatat(plan->parent, plan->temporary, &created, AT_SYMLINK_NOFOLLOW);
	output = openat(plan->parent, plan->temporary, O_RDONLY | O_NOFOLLOW | O_CLOEXEC);
	if (have_created && output >= 0 && !fstat(output, &current) &&
	    current.st_dev == created.st_dev && current.st_ino == created.st_ino &&
	    !fstat(plan->source, &after) && unchanged(&plan->before, &after) &&
	    ((current.st_mode & 07777) == plan->mode || !fchmod(output, plan->mode)) &&
	    !renameatx_np(plan->parent, plan->temporary, plan->parent, plan->name, RENAME_EXCL)) {
		published = 1;
		if (!futimens(output, NULL) && !fstat(output, &plan->st)) {
			if (plan->size) {
				struct radvisory advice = { 0, (int)plan->size };
				fcntl(output, F_RDADVISE, &advice);
			}
			plan->result = 1;
			measure(&publish_ns, started);
		} else {
			/* Never retry a write after publishing its output. */
			plan->result = -1;
			reject("publish_error");
			plan->saved_errno = errno;
		}
	}
	if (!published && have_created &&
	    !fstatat(plan->parent, plan->temporary, &current, AT_SYMLINK_NOFOLLOW) &&
	    current.st_dev == created.st_dev && current.st_ino == created.st_ino)
		unlinkat(plan->parent, plan->temporary, 0);
 out:
	if (output >= 0)
		close(output);
	close(plan->source);
	close(plan->parent);
}

static void execute_plan(struct clone_plan *plan, struct donor_directory *cache)
{
	int rank;
	plan->result = 0;
	/* Cache is addressed by immutable blob identity; every opened file is still
	 * independently verified. Worktree preference is only a search-order hint. */
	for (rank = -1; rank < donor_nr; rank++) {
		const char *source_name;
		struct stat before, after;
		int parent, source, i = -1;
		uint64_t start;
		if (rank < 0) {
			source = apfs_cache_open(&plan->expected_oid);
			if (source < 0) continue;
		} else {
			int preferred = cache->preferred < donor_nr ? cache->preferred : 0;
			i = !rank ? preferred : (rank <= preferred ? rank - 1 : rank);
			if (donors[i]->is_current || donors[i]->is_bare) continue;
			if (diagnostic) __atomic_fetch_add(&donor_probes, 1, __ATOMIC_RELAXED);
			parent = donor_parent_fd(cache, donors[i]->path, plan->path, &source_name);
			if (parent < 0) { reject("donor_missing"); continue; }
			source = openat(parent, source_name, O_RDONLY | O_NOFOLLOW | O_NONBLOCK | O_CLOEXEC);
			if (source < 0) { reject("donor_missing"); continue; }
		}
		start = stamp();
		if (fstat(source, &before) || !S_ISREG(before.st_mode) || before.st_flags ||
		    !(before.st_mode & S_IRUSR) || (uintmax_t)before.st_size != plan->size || flistxattr(source, NULL, 0, 0) != 0) {
			reject("donor_metadata"); close(source); continue;
		}
		if (!matches_blob_oid(source, plan->size, &plan->expected_oid, plan->hash_algo)) {
			reject("donor_mismatch"); close(source); continue;
		}
		if (fstat(source, &after) || !unchanged(&before, &after)) {
			reject("donor_changed"); close(source); continue;
		}
		measure(&verify_ns, start);
		parent = parent_fd(".", plan->path, &plan->name);
		if (parent < 0) { close(source); break; }
		plan->source = source;
		plan->parent = parent;
		plan->before = before;
		plan->from_cache = rank < 0;
		execute_clone(plan);
		if (plan->result) {
			if (plan->result > 0 && i >= 0) cache->preferred = i;
			return;
		}
	}
	reject("no_matching_donor");
}
static void count_clone(const struct clone_plan *plan)
{
	if (plan->result > 0) {
		cloned_files++;
		cloned_bytes += plan->size;
		if (plan->from_cache) cache_hits++;
	}
}
int apfs_checkout_clone(const struct cache_entry *ce, const char *path,
		       const struct conv_attrs *ca, const struct checkout *state, struct stat *st)
{
	struct clone_plan plan;
	if (batch_fallback || !prepare_plan(ce, path, ca, state, &plan)) return 0;
	execute_plan(&plan, &main_source_dir);
	count_clone(&plan);
	if (plan.result > 0) *st = plan.st;
	else if (plan.result < 0) errno = plan.saved_errno;
	return plan.result;
}
void apfs_checkout_cache_entry(const struct checkout *state, const struct cache_entry *ce)
{
	struct apfs_cache_stats stats;
	struct conv_attrs ca;
	struct stat st;
	struct object_id oid;
	const char *name;
	int parent, fd;
	unsigned long configured_limit = 0;
	if (!state->istate || repo_config_get_ulong(state->istate->repo, "apfs.cachelimit", &configured_limit) || !configured_limit) return;
	initialize();
	apfs_cache_stats(&stats, 0);
	if (!enabled || !stats.limit || state->base_dir_len || !S_ISREG(ce->ce_mode)) return;
	convert_attrs(state->istate, &ca, ce->name);
	if (!convert_attrs_preserve_bytes(&ca)) return;
	parent = parent_fd(".", ce->name, &name);
	if (parent < 0) return;
	fd = openat(parent, name, O_RDONLY | O_NOFOLLOW | O_NONBLOCK | O_CLOEXEC);
	close(parent);
	if (fd < 0) return;
	oidcpy(&oid, lookup_replace_object(the_repository, &ce->oid));
	if (!fstat(fd, &st) && S_ISREG(st.st_mode) && st.st_size > 0 && st.st_size <= 64 * 1024 * 1024 && !st.st_flags &&
	    flistxattr(fd, NULL, 0, 0) == 0) apfs_cache_store(&oid, fd);
	close(fd);
}
#ifndef NO_PTHREADS
#define APFS_BATCH_SIZE 256
#define APFS_MAX_WORKERS 8

struct clone_batch {
	struct clone_plan *plans;
	int ready, next, finished;
	pthread_mutex_t lock;
	pthread_cond_t changed;
};

struct clone_worker {
	struct clone_batch *batch;
	struct donor_directory source_dir;
};

static void *clone_batch_worker(void *data)
{
	struct clone_worker *worker = data;
	struct clone_batch *batch = worker->batch;
	for (;;) {
		int i;
		pthread_mutex_lock(&batch->lock);
		while (batch->next == batch->ready && !batch->finished)
			pthread_cond_wait(&batch->changed, &batch->lock);
		if (batch->next == batch->ready) {
			pthread_mutex_unlock(&batch->lock);
			clear_donor_directory(&worker->source_dir);
			return NULL;
		}
		i = batch->next++;
		pthread_mutex_unlock(&batch->lock);
		execute_plan(&batch->plans[i], &worker->source_dir);
	}
}
#endif

int apfs_checkout_batch(struct parallel_checkout_item *items, size_t nr,
			const struct checkout *state, int workers)
{
#ifndef NO_PTHREADS
	size_t pos;
	struct rlimit limit;
	int capacity = APFS_BATCH_SIZE, handled = 0, explicit_workers, leased = 0;
	uint64_t started = stamp();

	initialize();
	if (state->base_dir_len || !enabled) return 0;
	apfs_checkout_default_workers();
	if (!has_sources) return 0;
	if (workers > APFS_MAX_WORKERS)
		return 0;
	if (!getrlimit(RLIMIT_NOFILE, &limit) && limit.rlim_cur != RLIM_INFINITY) {
		if (limit.rlim_cur <= 64)
			return 0;
		if ((limit.rlim_cur - 64) / 3 < capacity)
			capacity = (limit.rlim_cur - 64) / 3;
		if (!capacity)
			return 0;
	}
	if (repo_config_get_int(the_repository, "checkout.workers", &explicit_workers) &&
	    !getenv("GIT_TEST_CHECKOUT_WORKERS")) {
		leased = apfs_budget_acquire(the_repository, workers - 1, worker_budget);
		workers = 1 + leased;
	}
	selected_workers = workers;
	if (diagnostic && leased) fprintf(stderr, "{\"event\":\"git-apfs-worker-lease\",\"process_id\":%d,\"at_ns\":%"PRIu64",\"delta\":%d}\n", getpid(), getnanotime(), leased);
	/* Bound pinned descriptors, including on systems with low RLIMIT_NOFILE.
	 * Object reads and all preparation remain serial and bounded per file. */
	for (pos = 0; pos < nr; ) {
		struct clone_plan plans[APFS_BATCH_SIZE];
		struct parallel_checkout_item *prepared[APFS_BATCH_SIZE];
		struct clone_batch batch = {
			.plans = plans,
			.lock = PTHREAD_MUTEX_INITIALIZER,
			.changed = PTHREAD_COND_INITIALIZER
		};
		struct clone_worker jobs[APFS_MAX_WORKERS];
		pthread_t threads[APFS_MAX_WORKERS];
		int started[APFS_MAX_WORKERS] = { 0 };
		int count = 0, i;

		memset(jobs, 0, sizeof(jobs));
		for (i = 0; i < workers; i++) {
			jobs[i].batch = &batch;
			jobs[i].source_dir.fd = -1;
		}
		for (; pos < nr && count < capacity; pos++) {
			struct parallel_checkout_item *item = &items[pos];
			if (!prepare_plan(item->ce, item->ce->name, &item->ca, state, &plans[count]))
				continue;
			prepared[count++] = item;
			if (count == 1) {
				handled = 1;
				batches++;
				batch_workers = 1;
				for (i = 1; i < workers; i++)
					if (!pthread_create(&threads[i], NULL, clone_batch_worker, &jobs[i])) {
						started[i] = 1;
						batch_workers++;
					}
			}
			/* Publish only completely prepared plans. Workers never access
			 * Git objects while the main thread prepares the next file. */
			pthread_mutex_lock(&batch.lock);
			batch.ready = count;
			pthread_cond_signal(&batch.changed);
			pthread_mutex_unlock(&batch.lock);
		}
		pthread_mutex_lock(&batch.lock);
		batch.finished = 1;
		pthread_cond_broadcast(&batch.changed);
		pthread_mutex_unlock(&batch.lock);
		/* The caller also drains work; thread-creation failure is harmless. */
		clone_batch_worker(&jobs[0]);
		for (i = 1; i < workers; i++)
			if (started[i] && pthread_join(threads[i], NULL))
				die("unable to join APFS checkout worker");
		pthread_cond_destroy(&batch.changed);
		pthread_mutex_destroy(&batch.lock);
		for (i = 0; i < count; i++) {
			count_clone(&plans[i]);
			if (plans[i].result > 0) {
				prepared[i]->st = plans[i].st;
				prepared[i]->status = PC_ITEM_WRITTEN;
			} else if (plans[i].result < 0) {
				errno = plans[i].saved_errno;
				error_errno("unable to finalize APFS checkout of %s", prepared[i]->ce->name);
				prepared[i]->status = PC_ITEM_FAILED;
			}
		}
	}
	measure(&batch_ns, started);
	if (diagnostic && leased) fprintf(stderr, "{\"event\":\"git-apfs-worker-lease\",\"process_id\":%d,\"at_ns\":%"PRIu64",\"delta\":%d}\n", getpid(), getnanotime(), -leased);
	apfs_budget_release();
	/* Auto policy keeps native fallbacks serial instead of spawning an
	 * unbudgeted process pool. Explicit worker settings retain Git behavior. */
	handled |= selected_workers == workers && repo_config_get_int(the_repository, "checkout.workers", &explicit_workers);
	batch_fallback = handled;
	return handled;
#else
	return 0;
#endif
}
int apfs_command(int argc, const char **argv, const char *prefix, struct repository *repo)
{
	int i;
	struct checkout state = CHECKOUT_INIT;
	(void)prefix;
	repo_config(repo, git_default_config, NULL);
	initialize();
	if (argc == 2 && (!strcmp(argv[1], "status") || !strcmp(argv[1], "doctor"))) {
		write_diagnostics(stdout, "git-apfs-status");
		return 0;
	}
	if (argc == 2 && !strcmp(argv[1], "tune")) {
		repo_config_set(repo, "core.fsmonitor", "true");
		repo_config_set(repo, "core.untrackedCache", "true");
		puts("Enabled FSMonitor and untracked-cache configuration. With APFS cloning or a donor cache enabled, FSMonitor is bypassed for safe stat validation.");
		return 0;
	}
	if (argc == 3 && !strcmp(argv[1], "cache") && !strcmp(argv[2], "status")) {
		write_diagnostics(stdout, "git-apfs-cache"); return 0;
	}
	if (argc == 3 && !strcmp(argv[1], "cache") && !strcmp(argv[2], "prune"))
		return apfs_cache_prune() ? error("cache unavailable or busy") : 0;
	if (argc == 3 && !strcmp(argv[1], "cache") && !strcmp(argv[2], "warm")) {
		struct apfs_cache_stats cache;
		if (!repo_get_work_tree(repo)) return error("cache warm requires a worktree");
		setup_work_tree(repo);
		apfs_cache_stats(&cache, 0);
		if (!cache.limit) return error("set apfs.cacheLimit to a positive byte budget before warming");
		if (repo_read_index(repo) < 0) return error("unable to read index");
		state.istate = repo->index;
		for (i = 0; i < repo->index->cache_nr; i++)
			if (!ce_stage(repo->index->cache[i]) && !(repo->index->cache[i]->ce_flags & CE_SKIP_WORKTREE))
				apfs_checkout_cache_entry(&state, repo->index->cache[i]);
		write_diagnostics(stdout, "git-apfs-cache-warm");
		return 0;
	}
	return error("usage: git apfs {status|doctor|tune|cache {status|warm|prune}}");
}

#else
int apfs_checkout_default_workers(void) { return 1; }
int apfs_checkout_large_batch(struct parallel_checkout_item *i UNUSED, size_t n UNUSED) { return 0; }
void apfs_checkout_finish_batch(void) { }
void apfs_checkout_cache_entry(const struct checkout *s UNUSED, const struct cache_entry *ce UNUSED) { }
int apfs_checkout_batch(struct parallel_checkout_item *i UNUSED, size_t n UNUSED, const struct checkout *s UNUSED, int w UNUSED) { return 0; }
int apfs_checkout_clone(const struct cache_entry *ce UNUSED, const char *p UNUSED, const struct conv_attrs *ca UNUSED, const struct checkout *s UNUSED, struct stat *st UNUSED) { return 0; }
int apfs_command(int argc UNUSED, const char **argv UNUSED, const char *prefix UNUSED, struct repository *repo UNUSED)
{
	return error("git apfs currently requires macOS APFS");
}
#endif
