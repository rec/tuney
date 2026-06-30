from .tuning import TuningP

EPSILON = 1e-6


def nearest_note(
    tuning: TuningP, frequency: float, epsilon: float = EPSILON
) -> int | tuple[int, int]:
    below = above = 0
    while tuning(below) > frequency:
        below = (2 * below) or -0x40
    while tuning(above) < frequency:
        above = (2 * above) or 0x40
    while (above - below) > 1:
        mid = (below + above) // 2
        f = tuning(mid)
        if abs(f - frequency) < epsilon:
            return mid
        elif f < frequency:
            below = mid
        else:
            above = mid
    return below, above
