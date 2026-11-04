// SPDX-License-Identifier: MIT
//! Pure validation prototype. Values are commands in microvolts, not measurements.
#![no_std]

/// Validate an already observed voltage command before a hypothetical transition.
/// Returns 0 for an acceptable command, -1 for unknown, -2 for invalid bounds,
/// and -3 when the current command is outside the permitted interval.
/// This function performs no I/O, allocations, pointer access, or voltage changes.
#[no_mangle]
pub extern "C" fn gf117_rust_validate_command(current_uv: i32, required_uv: i32, ceiling_uv: i32) -> i32 {
    if current_uv <= 0 {
        return -1;
    }
    if required_uv <= 0 || ceiling_uv <= 0 || required_uv > ceiling_uv {
        return -2;
    }
    if current_uv < required_uv || current_uv > ceiling_uv {
        return -3;
    }
    0
}
