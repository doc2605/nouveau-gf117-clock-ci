// SPDX-License-Identifier: MIT
#include <assert.h>
#include <limits.h>
#include <stdio.h>
extern int gf117_rust_validate_command(int, int, int);

static int reference(int current, int required, int ceiling)
{
    if (current <= 0) return -1;
    if (required <= 0 || ceiling <= 0 || required > ceiling) return -2;
    if (current < required || current > ceiling) return -3;
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
                assert(gf117_rust_validate_command(values[i], values[j], values[k]) ==
                       reference(values[i], values[j], values[k]));
                ++cases;
            }
    assert(gf117_rust_validate_command(-19, 850000, 1000000) == -1);
    assert(gf117_rust_validate_command(900000, 850000, 1000000) == 0);
    printf("PASS: %u C/Rust boundary combinations\n", cases);
}
