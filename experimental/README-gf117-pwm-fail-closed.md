# GF117 PWM voltage safety gate

The consolidated experimental patch exposed a PWM voltage setter and allowed
core-only preflight to continue when the current command was unavailable. A
PWM command is not an independent electrical voltage measurement, and the
regulator's initial state and GF117 write behavior are not established.

Patch 0046 leaves PWM readback available but removes the GF117 PWM write
backend, and rejects an unknown current command before attempting voltage,
fan or clock changes. Core-only reclocking may therefore be unavailable even
when a PWM regulator exists. This is an experimental safety restriction, not
proof that a readable PWM command equals the actual rail voltage or that any
clock transition is safe. GPIO voltage behavior and the PMU opt-in remain
separate and unvalidated.

`test-gf117-core-source.py` executes the actual preflight and cstate functions
with mocks, including a setter-present unreadable case; `test-gf117-pwm-voltage.py`
checks that the actual PWM backend has no setter and tests readback with mocks.
CI builds the resulting module but does not load it or exercise real hardware.

Patch 0047 fixes the generic Nouveau hwmon voltage callback: a failed read or
missing minimum/maximum is returned as an error rather than reported as a
negative numeric sensor value. The source-level mock test checks error paths,
units, missing bounds, and power-off behavior. This change affects Nouveau
voltage reporting on all chipsets; physical regression testing is not yet
available. It does not convert a PWM-derived command into a physical reading.
