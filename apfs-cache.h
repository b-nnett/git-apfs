#ifndef APFS_CACHE_H
#define APFS_CACHE_H
struct repository;
struct object_id;
struct apfs_cache_stats {
	uintmax_t limit, charged_bytes, entries, stored, evicted, hits;
	uintmax_t directory_bytes;
	int available, writer_busy;
};
void apfs_cache_init(struct repository *repo);
int apfs_cache_open(const struct object_id *oid);
int apfs_cache_store(const struct object_id *oid, int source);
int apfs_cache_prune(void);
void apfs_cache_stats(struct apfs_cache_stats *out, int refresh);
int apfs_budget_acquire(struct repository *repo, int wanted, int budget);
void apfs_budget_release(void);
#endif
