// SPDX-License-Identifier: MIT
//! Pure scalar mirror of Nouveau's GT215 PLL candidate calculator.
//!
//! Inputs come from the C-owned VBIOS PLL limits. The function does no MMIO,
//! allocation, pointer access, logging, or register programming. Results are
//! meaningful only when `ret > 0`; error returns leave coefficient fields at
//! zero. The caller must keep the C calculator as the authority until parity
//! tests cover the exact kernel source and GF117 integration path.
#![cfg_attr(not(CONFIG_RUST), no_std)]

/// Fixed-layout result shared with Nouveau's C PLL planner.
#[repr(C)]
pub struct Gf117PllResult {
    /// Achieved output frequency, or a negative errno on failure.
    pub ret: i32,
    /// Integer feedback divider (N) selected by the PLL solver.
    pub n: i32,
    /// Fractional feedback field; unused by the current GF117 C caller.
    pub f_n: i32,
    /// Reference input divider (M) selected by the PLL solver.
    pub m: i32,
    /// Output post-divider (P) selected by the PLL solver.
    pub p: i32,
}

const EINVAL: i32 = -22;
const ERANGE: i32 = -34;
const INT_MAX: u64 = i32::MAX as u64;

fn failure(ret: i32) -> Gf117PllResult {
    Gf117PllResult { ret, n: 0, f_n: 0, m: 0, p: 0 }
}

/// Calculate a GT215-style PLL candidate from scalar VBIOS bounds.
///
/// `fractional != 0` selects Nouveau's optional fractional-N path. Return
/// values and successful coefficient fields follow `gt215_pll_calc()`.
#[no_mangle]
pub extern "C" fn gf117_rust_gt215_pll_calc(
    refclk: u32,
    max_freq: u32,
    min_inputfreq: u32,
    max_inputfreq: u32,
    min_m: u32,
    max_m: u32,
    min_n: u32,
    max_n: u32,
    min_p: u32,
    max_p: u32,
    freq: u32,
    fractional: u32,
) -> Gf117PllResult {
    if freq == 0
        || refclk == 0
        || max_freq == 0
        || min_inputfreq == 0
        || max_inputfreq == 0
        || min_m == 0
        || min_m > max_m
        || min_n == 0
        || min_n > max_n
        || min_p == 0
        || min_p > max_p
        || min_inputfreq > max_inputfreq
        || max_m > u8::MAX as u32
        || max_n > u8::MAX as u32
        || max_p > u8::MAX as u32
    {
        return failure(EINVAL);
    }
    if freq as u64 > INT_MAX {
        return failure(ERANGE);
    }

    let Some(quotient) = max_freq.checked_div(freq) else {
        return failure(ERANGE);
    };
    // C assigns this u32 quotient to signed int before clamping. Linux uses
    // two's-complement signed integers; mirror that conversion for parity.
    let mut p = quotient as i32;
    if p > max_p as i32 {
        p = max_p as i32;
    }
    if p < min_p as i32 {
        p = min_p as i32;
    }
    if p == 0 {
        return failure(ERANGE);
    }

    let Some(low_m_numerator) = (refclk as u64).checked_add(max_inputfreq as u64 - 1) else {
        return failure(ERANGE);
    };
    let Some(low_m_quotient) = low_m_numerator.checked_div(max_inputfreq as u64) else {
        return failure(ERANGE);
    };
    if low_m_quotient > INT_MAX {
        return failure(ERANGE);
    }
    let low_m = (low_m_quotient as u32).max(min_m);
    let Some(high_m_quotient) = refclk.checked_div(min_inputfreq) else {
        return failure(ERANGE);
    };
    if high_m_quotient as u64 > INT_MAX {
        return failure(ERANGE);
    }
    let high_m = high_m_quotient.min(max_m);
    if low_m > high_m {
        return failure(ERANGE);
    }

    let mut best_error = u64::MAX;
    let mut best_n = 0i32;
    let mut best_m = 0i32;

    for m in low_m..=high_m {
        let numerator = freq as u64 * p as u64 * m as u64;
        let Some(quotient) = numerator.checked_div(refclk as u64) else {
            return failure(ERANGE);
        };
        let Some(remainder) = numerator.checked_rem(refclk as u64) else {
            return failure(ERANGE);
        };
        if quotient > INT_MAX {
            return failure(ERANGE);
        }
        let mut n = quotient as i32;
        let mut f_n = 0i32;

        if fractional == 0 {
            if remainder >= (refclk / 2) as u64 {
                if n == i32::MAX {
                    return failure(ERANGE);
                }
                n += 1;
            }
        } else {
            if remainder < (refclk / 2) as u64 {
                n -= 1;
            }
            let fractional = numerator as i64 - n as i64 * refclk as i64;
            if fractional < i32::MIN as i64 || fractional > i32::MAX as i64 {
                return failure(ERANGE);
            }
            f_n = fractional as i32;
        }

        if n < min_n as i32 {
            continue;
        }
        if n > max_n as i32 {
            break;
        }

        let Some(actual) = (refclk as u64 * n as u64)
            .checked_div(m as u64)
            .and_then(|actual| actual.checked_div(p as u64))
        else {
            return failure(ERANGE);
        };
        let error = if actual > freq as u64 {
            actual - freq as u64
        } else {
            freq as u64 - actual
        };
        if error < best_error {
            best_error = error;
            best_n = n;
            best_m = m as i32;
        }

        if fractional != 0 {
            // f_n is nonnegative on this branch, matching C's signed shift.
            let scaled = (f_n as i64) * 8192 + refclk as i64 / 2;
            let Some(scaled_fraction) = scaled
                .checked_div(refclk as i64)
                .map(|scaled| (scaled - 4096) & 0xffff)
            else {
                return failure(ERANGE);
            };
            return Gf117PllResult {
                ret: freq as i32,
                n,
                f_n: scaled_fraction as i32,
                m: m as i32,
                p,
            };
        }
    }

    if best_error == u64::MAX {
        return failure(EINVAL);
    }
    if best_m == 0 || p == 0 {
        return failure(ERANGE);
    }
    let Some(actual) = (refclk as u64 * best_n as u64)
        .checked_div(best_m as u64)
        .and_then(|actual| actual.checked_div(p as u64))
    else {
        return failure(ERANGE);
    };
    if actual > INT_MAX {
        return failure(ERANGE);
    }
    Gf117PllResult {
        ret: actual as i32,
        n: best_n,
        f_n: 0,
        m: best_m,
        p,
    }
}
