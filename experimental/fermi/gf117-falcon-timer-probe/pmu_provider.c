/* SPDX-License-Identifier: MIT */
/*
 * Experimental NVKM provider for the GF117 timer diagnostic.
 * It is selected only through NvGf117TimerProbe (default false), and the
 * constructor has a compile-time recovery gate that stays closed until an
 * independent Falcon recovery procedure has been demonstrated.
 */
#include "priv.h"
#include "fuc/gf117_timer_probe.fuc3.h"
#include "host.h"

#include <core/option.h>

#define GF117_TIMER_PROBE_RECOVERY_VERIFIED 0
#define GF117_TIMER_PROBE_SAMPLES 8

static int
gf117_timer_probe_pmu_init(struct nvkm_pmu *pmu)
{
	struct gf117_timer_probe_sample samples[GF117_TIMER_PROBE_SAMPLES];
	int ret;

	ret = gt215_pmu_init(pmu);
	if (ret)
		return ret;

	return gf117_timer_probe_collect_pmu(pmu, samples,
					     ARRAY_SIZE(samples));
}

static const struct nvkm_pmu_func
gf117_timer_probe_pmu = {
	.flcn = &gt215_pmu_flcn,
	.code.data = gf117_timer_probe_pmu_code,
	.code.size = sizeof(gf117_timer_probe_pmu_code),
	.data.data = gf117_timer_probe_pmu_data,
	.data.size = sizeof(gf117_timer_probe_pmu_data),
	.enabled = gf100_pmu_enabled,
	.reset = gf100_pmu_reset,
	.init = gf117_timer_probe_pmu_init,
	.fini = gt215_pmu_fini,
	.intr = gt215_pmu_intr,
	.send = gt215_pmu_send,
	.recv = gt215_pmu_recv,
};

static const struct nvkm_pmu_fwif
gf117_timer_probe_fwif[] = {
	{ -1, gf100_pmu_nofw, &gf117_timer_probe_pmu },
	{}
};

int gf117_timer_probe_pmu_new(struct nvkm_device *, enum nvkm_subdev_type,
			      int, struct nvkm_pmu **);

int
gf117_timer_probe_pmu_new(struct nvkm_device *device,
			  enum nvkm_subdev_type type, int inst,
			  struct nvkm_pmu **ppmu)
{
	if (!ppmu)
		return -EINVAL;
	*ppmu = NULL;
	if (!device || device->chipset != 0xd7 ||
	    !nvkm_boolopt(device->cfgopt, "NvGf117TimerProbe", false))
		return -ENODEV;
	if (!GF117_TIMER_PROBE_RECOVERY_VERIFIED)
		return -EOPNOTSUPP;

	return nvkm_pmu_new_(gf117_timer_probe_fwif, device, type, inst, ppmu);
}
