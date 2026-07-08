# From scipy
# Author: Travis Oliphant
# 2003
from numpy import asarray, extract, mod, nan, pi, place, zeros

__all__ = ['sawtooth', 'square']


def sawtooth(t, width=1):
    """
    Return a periodic sawtooth or triangle waveform.

    The sawtooth waveform has a period ``2*pi``, rises from -1 to 1 on the
    interval 0 to ``width*2*pi``, then drops from 1 to -1 on the interval
    ``width*2*pi`` to ``2*pi``. `width` must be in the interval [0, 1].

    Note that this is not band-limited.  It produces an infinite number
    of harmonics, which are aliased back and forth across the frequency
    spectrum.
    """
    t, w = asarray(t), asarray(width)
    w = asarray(w + (t - t))
    t = asarray(t + (w - w))
    y = zeros(t.shape, dtype='d')

    mask1 = (w > 1) | (w < 0)
    place(y, mask1, nan)

    tmod = mod(t, 2 * pi)

    mask2 = (1 - mask1) & (tmod < w * 2 * pi)
    tsub = extract(mask2, tmod)
    wsub = extract(mask2, w)
    place(y, mask2, tsub / (pi * wsub) - 1)

    mask3 = (1 - mask1) & (1 - mask2)
    tsub = extract(mask3, tmod)
    wsub = extract(mask3, w)
    place(y, mask3, (pi * (wsub + 1) - tsub) / (pi * (1 - wsub)))
    return y


def square(t, duty=0.5):
    """
    Return a periodic square-wave waveform.

    The square wave has a period ``2*pi``, has value +1 from 0 to
    ``2*pi*duty`` and -1 from ``2*pi*duty`` to ``2*pi``. `duty` must be in
    the interval [0,1].

    Note that this is not band-limited.  It produces an infinite number
    of harmonics, which are aliased back and forth across the frequency
    spectrum.
    """
    t, w = asarray(t), asarray(duty)
    w = asarray(w + (t - t))
    t = asarray(t + (w - w))
    y = zeros(t.shape, dtype='d')

    mask1 = (w > 1) | (w < 0)
    place(y, mask1, nan)

    tmod = mod(t, 2 * pi)
    mask2 = (1 - mask1) & (tmod < w * 2 * pi)
    place(y, mask2, 1)

    mask3 = (1 - mask1) & (1 - mask2)
    place(y, mask3, -1)
    return y
