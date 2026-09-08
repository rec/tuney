# Shared musical definitions

Tuney consumes [Ufor](https://github.com/rec/ufor) for scale naming,
accidentals, pitch arithmetic, tuning definitions, Scala text conversion, and
oscillator parameters/gain. Ufor has no dependency on Tuney or its audio/UI stack.
Its [musical specification](../../ufor/doc/musical-format.md) and
[JSON Schema](../../ufor/schema/documents.json) describe the portable documents.

Keep Ufor checked out at `../ufor` for local UV development, then run `uv sync`.
The package dependency pins a public source archive for installations and
release builds that disable UV development sources. Git remotes remain SSH.

Tuney's `Scale` and `Oscillator` subclasses retain the existing UI/CLI field
annotations and mutable configuration. Scale calculations and oscillator gain
come from Ufor. NumPy waveform generation remains in `tuney/audio/oscillator.py`.
There is no second waveform engine or new sampler.

Computed, ratio, table, and tuning configuration classes expose `definition`
values owned by Ufor. Configuration selectors, inactive edits, units, and the
broader expression evaluator remain in Tuney. Fractions and `^` expressions can
be authored in ratio text. `Computed.limit` means maximum rational denominator,
not a prime-limit JI tuning.

A portable frequency table is finite and rejects indexes beyond either end.
Tuney's `Tuning` explicitly wraps instrument keys before reading the table,
preserving existing playability. Exported tuning definitions place the table at
the configured reference note and do not include that application wrapping rule.
Ratios may repeat with an explicit multiplier; adjacent intervals may repeat
with an explicit step pattern. Scala file encoding and browsing remain local;
conversion of Scala text into shared ratios belongs to Ufor.

The shared codec handles tuning, scale, and oscillator documents. The initial
extraction retains the common `format = "recs"` and version 1 marker. Envelope,
LFO, phase/retrigger, and final instrument contracts remain future model work.
