# My master plan

I already have these, under /Users/tom/code/:

Working:
* tuney: turn text into audio (beta)
* recs: automatically record all audio and keyboard events (beta)
* fmix: make mixes of recordings (beta)

Sketches
* lespistes: share fmixes (text-only)
* litoid: automatically record all DMX events (strong alpha)
* vl8: process existing audio into new audio (lots of code of various quality)

The idea is to build a universal recorder that records, processes, mixes and plays back all time data except video:

* audio
* MIDI
* DMX
* keystrokes
* OSC/artnet
* other real time protocols

Mixes are human-readable and can use URIs.

Quantity data is stored in tensors, either numpy.ndarray or torch.tensor
