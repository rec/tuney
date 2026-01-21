New definitions:

* tuning: a mapping from note numbers to frequencies
* scale: a tuning, *plus* a naming system for notes

So scales can share a tuning, but not the same names (like CDE vs solfege); or they can
share the names but not the tuning (like 12TET vs some 12-tone just intonation)

----

## Naming non-standard scales by extending the standard 12tet naming system.

12tet has the following dramatis personae.

* The note names, a subsequence of letters ABCDEFG from A-Z.
* A start note, C.
* Two modifiers, ♭ and ♯
* The semitone differences from the start note: 2212221

Let's fix the alphabet, alphabetic order, and the two modifiers as givens, and also
disallow "wrap around" names like XYZABC as confusing.

What we can vary are these:

* the position of the note name sequence within A-Z (in 12tet it's A)
* the length of the note name sequence (8)
* the start note (C)
* the subtone differences between pairs of notes (in 12tet, it's 2212221)

If we allowed just one sharp or flat symbol, the maximum subtone difference between letter
notes is 3: A, A♯, B♭ and B would be four separate notes.

For the first pass, again to be familiar to musicians, we're going to restrict
the choice to just 1 and 2.
