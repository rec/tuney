from .scale import Scale

EPSILON = 1e-6


def nearest_note(
    scale: Scale, frequency: float, epsilon: float = EPSILON
) -> int | tuple[int, int]:
    below = above = 0
    while scale(below) > frequency:
        below = (2 * below) or -0x40
    while scale(above) < frequency:
        above = (2 * above) or 0x40
    while (above - below) > 1:
        mid = (below + above) // 2
        f = scale(mid)
        if abs(f - frequency) < epsilon:
            return mid
        elif f < frequency:
            below = mid
        else:
            above = mid
    return below, above
