#include "git-compat-util.h"
#include "builtin.h"
#include "apfs-checkout.h"

int cmd_apfs(int argc, const char **argv, const char *prefix, struct repository *repo)
{
	show_usage_if_asked(argc, argv, "git apfs {status|doctor|tune|cache {status|warm|prune}}");
	return apfs_command(argc, argv, prefix, repo);
}
