from __future__ import annotations

from collections.abc import Hashable


class Modifiers(int):
    none = 0

    alt = 1
    alt_l = 2 * alt
    alt_r = 2 * alt_l
    alt_gr = 2 * alt_r

    cmd = 2 * alt_gr
    cmd_l = 2 * cmd
    cmd_r = 2 * cmd_l

    ctrl = 2 * cmd_r
    ctrl_l = 2 * ctrl
    ctrl_r = 2 * ctrl_l

    shift = 2 * ctrl_r
    shift_l = 2 * shift
    shift_r = 2 * shift_l

    alts = alt | alt_l | alt_r | alt_gr
    cmds = cmd | cmd_l | cmd_r
    ctrls = ctrl | ctrl_l | ctrl_r
    shifts = shift | shift_l | shift_r

    @property
    def has_alt(self) -> bool:
        return bool(self.alts & self)

    @property
    def has_cmd(self) -> bool:
        return bool(self.cmds & self)

    @property
    def has_ctrl(self) -> bool:
        return bool(self.ctrls & self)

    @property
    def has_shift(self) -> bool:
        return bool(self.shifts & self)

    @property
    def is_command(self) -> bool:
        return self.has_alt or self.has_cmd or self.has_ctrl

    def apply(self, key: Hashable | None, is_press: bool) -> Modifiers:
        if mask := getattr(Modifiers, str(getattr(key, 'name', '')), None):
            return Modifiers((self | mask) if is_press else (self & ~mask))
        return self
