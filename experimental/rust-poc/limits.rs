// SPDX-License-Identifier: MIT
//! Pure validator for VBIOS-derived voltage plans, not rail measurements.
#![cfg_attr(not(CONFIG_RUST), no_std)]

/// Validate a VBIOS-derived voltage target against the VBIOS interval.
/// Returns 0 for an acceptable target, -1 for an unknown target, -2 for invalid
/// bounds, and -3 when the target falls outside the permitted interval.
#[no_mangle]
pub extern "C" fn gf117_rust_validate_voltage_range(target_uv: i32, min_uv: i32, max_uv: i32) -> i32 {
    if target_uv <= 0 {
        return -1;
    }
    if min_uv <= 0 || max_uv <= 0 || min_uv > max_uv {
        return -2;
    }
    if target_uv < min_uv || target_uv > max_uv {
        return -3;
    }
    0
}
