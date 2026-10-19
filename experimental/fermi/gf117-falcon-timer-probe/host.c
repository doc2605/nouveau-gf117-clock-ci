// SPDX-License-Identifier: MIT
/* Standalone timer-only request loop; not linked into Nouveau. */
#include "host.h"

#ifdef __KERNEL__
#include <linux/errno.h>
#else
#include <errno.h>
#endif

#define GF117_PROC_TEST 0x54534554U
/* Dedicated image echoes any message; reserve this ID for the timer probe. */
#define GF117_TIMER_PROBE_MESSAGE 0x47544631U
#define GF117_TIMER_PROBE_MIN_SAMPLES 8
#define GF117_TIMER_PROBE_MAX_SAMPLES 32

int
gf117_timer_probe_collect(const struct gf117_timer_probe_ops *ops,
			  void *context,
			  struct gf117_timer_probe_sample *samples,
			  unsigned int count)
{
	unsigned int i;

	if (!ops || !ops->send || !ops->clock_raw_ns || !samples)
		return -EINVAL;
	if (count < GF117_TIMER_PROBE_MIN_SAMPLES ||
	    count > GF117_TIMER_PROBE_MAX_SAMPLES)
		return -ERANGE;

	for (i = 0; i < count; i++) {
		u32 reply[2] = { 0, 0 };
		int ret;

		samples[i].timer_low = 0;
		samples[i].status = -EINPROGRESS;
		samples[i].host_before_ns = ops->clock_raw_ns(context);
		ret = ops->send(context, reply, GF117_PROC_TEST,
				GF117_TIMER_PROBE_MESSAGE, i, 0);
		samples[i].host_after_ns = ops->clock_raw_ns(context);
		samples[i].status = ret;
		if (ret)
			return ret; /* One timeout/error ends the run; never retry. */
		if (samples[i].host_after_ns <= samples[i].host_before_ns)
			return samples[i].status = -ERANGE;
		if (reply[1])
			return samples[i].status = -EPROTO;
		samples[i].timer_low = reply[0];
		if (i && samples[i].timer_low < samples[i - 1].timer_low)
			return samples[i].status = -EOVERFLOW;
	}

	for (i = 1; i < count; i++) {
		if (samples[i].timer_low != samples[0].timer_low)
			return 0;
	}
	return -ENODATA;
}

#ifdef __KERNEL__
#include <linux/ktime.h>
#include <nvkm/subdev/pmu.h>

static int
gf117_timer_probe_send(void *context, u32 reply[2], u32 process,
			 u32 message, u32 data0, u32 data1)
{
	return nvkm_pmu_send(context, reply, process, message, data0, data1);
}

static u64
gf117_timer_probe_clock(void *context)
{
	(void)context;
	return ktime_get_raw_ns();
}

int
gf117_timer_probe_collect_pmu(struct nvkm_pmu *pmu,
			      struct gf117_timer_probe_sample *samples,
			      unsigned int count)
{
	static const struct gf117_timer_probe_ops ops = {
		.send = gf117_timer_probe_send,
		.clock_raw_ns = gf117_timer_probe_clock,
	};
	unsigned int i;
	int ret;

	if (!samples || count > GF117_TIMER_PROBE_MAX_SAMPLES)
		return -EINVAL;
	for (i = 0; i < count; i++)
		samples[i].status = -ECANCELED;

	ret = gf117_timer_probe_collect(&ops, pmu, samples, count);
	for (i = 0; i < count; i++) {
		if (samples[i].status == -ECANCELED)
			break;
		nvkm_info(&pmu->subdev,
			 "gf117_timer_probe seq=%u begin_ns=%llu end_ns=%llu timer=0x%08x status=%d\n",
			 i,
			 (unsigned long long)samples[i].host_before_ns,
			 (unsigned long long)samples[i].host_after_ns,
			 samples[i].timer_low, samples[i].status);
	}
	if (ret == -ENODATA)
		nvkm_warn(&pmu->subdev, "Falcon TIMER_LOW did not advance across %u replies\n", count);
	else if (ret == -EOVERFLOW)
		nvkm_warn(&pmu->subdev, "Falcon TIMER_LOW decreased; wrap/reset is ambiguous\n");
	return ret;
}
#endif
