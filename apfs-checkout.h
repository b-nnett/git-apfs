#ifndef APFS_CHECKOUT_H
#define APFS_CHECKOUT_H

struct cache_entry;
struct conv_attrs;
struct checkout;
struct stat;
struct parallel_checkout_item;

int apfs_checkout_default_workers(void);
int apfs_checkout_batch(struct parallel_checkout_item *items, size_t nr,
			const struct checkout *state, int workers);

/* Returns 1 for a clone, 0 for native fallback, -1 for a published-write error. */
int apfs_checkout_clone(const struct cache_entry *ce, const char *path,
		       const struct conv_attrs *ca,
		       const struct checkout *state, struct stat *st);
#endif
