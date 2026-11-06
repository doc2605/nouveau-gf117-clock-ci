// SPDX-License-Identifier: MIT
#include <assert.h>
#include <limits.h>
#include <stdio.h>
extern int gf117_rust_validate_voltage_range(int, int, int);

static int reference(int target, int min, int max)
{
    if (target <= 0) return -1;
    if (min <= 0 || max <= 0 || min > max) return -2;
    if (target < min || target > max) return -3;
    return 0;
}
int main(void)
{
    const int values[] = { INT_MIN, -19, -1, 0, 1, 2, 649999, 650000,
                           900000, 1000000, 1200000, INT_MAX };
    unsigned int cases = 0;
    for (unsigned int i = 0; i < sizeof(values)/sizeof(values[0]); ++i)
        for (unsigned int j = 0; j < sizeof(values)/sizeof(values[0]); ++j)
            for (unsigned int k = 0; k < sizeof(values)/sizeof(values[0]); ++k) {
                assert(gf117_rust_validate_voltage_range(values[i], values[j], values[k]) ==
                       reference(values[i], values[j], values[k]));
                ++cases;
            }
    assert(gf117_rust_validate_voltage_range(-19, 850000, 1000000) == -1);
    assert(gf117_rust_validate_voltage_range(900000, 850000, 1000000) == 0);
    printf("PASS: %u C/Rust boundary combinations\n", cases);
}
