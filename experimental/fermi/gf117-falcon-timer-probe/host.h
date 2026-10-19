/* SPDX-License-Identifier: MIT */
#ifndef GF117_FALCON_TIMER_PROBE_HOST_H
#define GF117_FALCON_TIMER_PROBE_HOST_H

#ifdef __KERNEL__
#include <linux/types.h>
#else
#include <stdint.h>
typedef uint32_t u32;
typedef uint64_t u64;
#endif

struct gf117_timer_probe_sample {
	u64 host_before_ns;
	u64 host_after_ns;
	u32 timer_low;
	int status;
};

struct gf117_timer_probe_ops {
	int (*send)(void *context, u32 reply[2], u32 process, u32 message,
		    u32 data0, u32 data1);
	u64 (*clock_raw_ns)(void *context);
};

int gf117_timer_probe_collect(const struct gf117_timer_probe_ops *,
			      void *context,
			      struct gf117_timer_probe_sample *, unsigned int count);

#ifdef __KERNEL__
struct nvkm_pmu;
int gf117_timer_probe_collect_pmu(struct nvkm_pmu *,
				  struct gf117_timer_probe_sample *, unsigned int count);
#endif

#endif
