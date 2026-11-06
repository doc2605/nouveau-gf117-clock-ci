// SPDX-License-Identifier: MIT
//! Pure scalar mirror of Nouveau's GT215 PLL candidate calculator.
//!
//! Inputs come from the C-owned VBIOS PLL limits. The function does no MMIO,
//! allocation, pointer access, logging, or register programming. Results are
//! meaningful only when `ret > 0`; error returns leave coefficient fields at
//! zero. The caller must keep the C calculator as the authority until parity
//! tests cover the exact kernel source and GF117 integration path.
#![cfg_attr(not(CONFIG_RUST), no_std)]

#[repr(C)]
pub struct Gf117PllResult {
    pub ret: i32,
    pub n: i32,
    pub f_n: i32,
    pub m: i32,
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

    let mut p = max_freq / freq;
    p = p.min(max_p).max(min_p);
    if p == 0 {
        return failure(ERANGE);
    }

    let low_m_quotient = (refclk as u64 + max_inputfreq as u64 - 1)
        / max_inputfreq as u64;
    if low_m_quotient > INT_MAX {
        return failure(ERANGE);
    }
    let low_m = (low_m_quotient as u32).max(min_m);
    let high_m_quotient = refclk / min_inputfreq;
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
        let quotient = numerator / refclk as u64;
        let remainder = (numerator % refclk as u64) as u32;
        if quotient > INT_MAX {
            return failure(ERANGE);
        }
        let mut n = quotient as i32;
        let mut f_n = 0i32;

        if fractional == 0 {
            if remainder >= refclk / 2 {
                if n == i32::MAX {
                    return failure(ERANGE);
                }
                n += 1;
            }
        } else {
            if remainder < refclk / 2 {
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

        let actual = refclk as u64 * n as u64 / m as u64 / p as u64;
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
            let scaled_fraction = ((scaled / refclk as i64) - 4096) & 0xffff;
            return Gf117PllResult {
                ret: freq as i32,
                n,
                f_n: scaled_fraction as i32,
                m: m as i32,
                p: p as i32,
            };
        }
    }

    if best_error == u64::MAX {
        return failure(EINVAL);
    }
    if best_m == 0 || p == 0 {
        return failure(ERANGE);
    }
    let actual = refclk as u64 * best_n as u64 / best_m as u64 / p as u64;
    if actual > INT_MAX {
        return failure(ERANGE);
    }
    Gf117PllResult {
        ret: actual as i32,
        n: best_n,
        f_n: 0,
        m: best_m,
        p: p as i32,
    }
}
