// SPDX-License-Identifier: MIT
/* Kbuild proof of C calling Rust: no GPU interaction and no auto-install. */
#include <linux/errno.h>
#include <linux/init.h>
#include <linux/module.h>

extern int gf117_rust_validate_command(int current_uv, int required_uv, int ceiling_uv);

static int __init gf117_rust_poc_init(void)
{
	return gf117_rust_validate_command(900000, 850000, 1000000) ? -EINVAL : 0;
}

static void __exit gf117_rust_poc_exit(void) { }
module_init(gf117_rust_poc_init);
module_exit(gf117_rust_poc_exit);
MODULE_LICENSE("Dual MIT/GPL");
MODULE_DESCRIPTION("GF117 Rust validation integration proof; no hardware access");
