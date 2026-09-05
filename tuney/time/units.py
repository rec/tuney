from reccy import units

SEC_IN_MS = 1000.0


def to_ms(s: units.Seconds) -> units.Milliseconds:
    return s * SEC_IN_MS


def to_seconds(m: units.Milliseconds) -> units.Seconds:
    return m / SEC_IN_MS
