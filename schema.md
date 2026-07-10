# Tuney data classes

```
class Tuney:
    """Turn text into music.

    Use positional `TEXT` to play characters as notes, then tune the scale,
    audio, MIDI, and timing from the same config model.
    """
    # Convert letters to scale indexes
    mapper: Mapper

    # Convert scale indexes to note names and note numbers
    scale: Scale

    # Convert note numbers into frequencies
    tuning: Tuning

    # Audio output device settings
    device: Device

    # Synthesizer sound settings
    sound: Sound

    # Where to send MIDI output
    midi: MIDI

    # Timings for playing back texts
    text_timings: TextTimings

    # Maximum silent gap to keep in recordings, in seconds
    max_gap: float = 4.0

    # Time to hover over a widget before showing help, in seconds
    hover_time: float = 1.0

    # Disable synthesized audio output
    silent: bool = False

    # If True, listen to the keyboard even when other applications are in front
    run_in_background: bool = False

    # Named performance preset to load
    preset: str | None = None


class Mapper:
    map: Map = Map.linear

    # Characters mapped to note numbers, or the default alphabet if empty
    alphabet: str | None = None

    # Number of note numbers to cycle through; zero uses the full alphabet
    length: int = 0

    # Treat uppercase and lowercase characters as distinct
    case_sensitive: bool = True

    # Reverse the order of mapped note numbers
    invert: bool = False

    # Offset from the center of the mapped note range
    offset: int = 0

    # Limit pitch range to this many notes
    range_limit: int = 60

    # What to do when mapped notes are outside the pitch range
    limiter: Limiter = Limiter.wrap


class Scale:
    """A generalized musical Scale, where the default is "regular tuning".

    The common Western scale has
    * 12 equal-tempered semitones per octave
    * Note names CDEFGAB, with intervals of 2212221 semitones between them
    * FLAT to lower pitch by a semitone, SHARP to raise it

    Scale generalizes this to allow more or less than 12 notes per octave, N-just limit,
    custom tunings, different note names and intervals.
    """
    #: The base note names
    note_names: str = string.ascii_uppercase

    #: The root note to start scales with
    root: str = 'C'

    #: The first note from the note names:
    # TODO: validate begin <= base <= end
    begin: str = 'A'

    #: The Last note from the alphabet
    end: str = 'G'

    # If `notes` is set, once the scale is generated, only the notes in
    # `notes` are actually used in the list.
    #
    # For example, notes='CDEFGAB' would correspond to only
    # the white notes on the piano.
    notes: str | None = None

    # The intervals between notes. Can also be entered as a string: "2212221"
    intervals: list[int]

    # Which accidentals are allowed in note names
    accidentals: Accidentals = Accidentals.whole

    #: Offset all note numbers by this
    offset: int = 0


class Computed:
    #: If limit is greater than zero, use rounded N-limit just intonation
    limit: int = 0

    #: Number of divisions of an octave
    notes_per_octave: int = 12

    #: Frequency change between octaves. For the default "power" pitch_to_frequency
    #: the change is a ratio, so if it's 2, each octave is twice the frequency of the
    #: last; for "linear", it's a difference, so if it's 100, each octave would be
    #: 100Hz greater in frequency than the previous.
    octave_ratio: float = 2


class Tuning:
    """
    A generalization of equal temperament, where the default values
    are the same as classic twelve-tone equal temperament (12-tet) but
    can be customized.
    """
    #: Which tuning source to use
    type: Type | None = Type.computed

    #: Computed tuning parameters
    computed: Computed | None

    #: Absolute frequencies, indexed by note number
    table: Table | None = None

    #: Ratio expressions, relative to root_frequency
    ratios: Ratios | None = None

    #: Detune everything, in cents of an octave division
    detune: float = 0

    #: The frequency of the reference `root_note`
    root_frequency: float = 440

    #: The note number of the reference note
    root_note: NoteNumber = 69


class Table:
    #: Absolute frequency expressions, indexed by note number
    text: str = ''


class Ratios:
    #: Ratio expressions for each step in the scale
    text: str = ''

    #: Name of this ratio scale
    name: str = ''

    #: Description of this ratio scale
    desc: str = ''


class Device:
    # Audio output sample rate, in frames per second
    sample_rate: int | None = None

    # Audio output device name or index
    device: int | str | None = None

    # Sample data type sent to the audio output device
    dtype: DType | None = None

    blocksize: int | None = None

    channels: int | None = None


class Sound:
    # Synthesizer oscillator settings
    oscillator: Oscillator

    # Audio output gain
    gain: float = 1.0

    # Offset added to generated note numbers before tuning
    note_offset: NoteNumber = 44

    polyphony: Polyphony

    # Minimum duration of each synthesized note, in seconds
    minimum_note_time: float = 0.5


class Oscillator:
    # Waveform used to synthesize notes
    waveform: Waveform = Waveform.triangle

    # Fraction of each waveform cycle before its falling edge
    duty_cycle: float = 0.5

    # Note number with no keyboard gain adjustment
    key_scale_note: NoteNumber = 64

    # Gain decibels added per keyboard octave above key_scale_note
    key_scale: float = 0.0


class Polyphony:
    # Divisor applied to mixed voices to provide polyphonic headroom
    headroom: float = 4

    # Maximum number of notes that can play simultaneously
    max_voices: int = 32


class MIDI:
    # Enable MIDI output
    enable: bool = False

    # MIDI output port name
    output: str | None = None

    # MIDI channel, from 0 to 15
    channel: int = 0

    # Velocity used for MIDI note-on messages
    velocity: int = 64

    # Offset added to MIDI note numbers
    note_offset: int = 0


class TextTimings:
    # Base duration for a space, in milliseconds
    space: Milliseconds = 100

    # Base duration for a dot, in milliseconds
    dot: Milliseconds = 300

    # Base duration for a comma, in milliseconds
    comma: Milliseconds = 200

    # Base duration for a colon, in milliseconds
    colon: Milliseconds = 400

    # Base duration for a semicolon, in milliseconds
    semicolon: Milliseconds = 400

    # Base duration for a blank line, in milliseconds
    blank_line: Milliseconds = 1000

    # Time that consecutive characters overlap, in milliseconds
    overlap: Milliseconds = 20

    # Seed for randomized character timings, or a random seed if empty
    seed: int | None = None

    # Ignore characters without an explicit timing unless they are alphabetic
    alpha_only: bool = True

    # Remove accents before generating character events
    strip_accents: bool = True

    # Multiplier applied to all generated timing values
    scale: float = 1.0

    # Additional per-character base durations, in milliseconds
    other: dict[str, Milliseconds]

    # Possible durations for alphabetic characters, in milliseconds
    timings: list[Milliseconds] | None = None

```
