from collections.abc import Callable
from enum import StrEnum, auto

from customtkinter import CTkButton, CTkFrame, CTkImage
from PIL import Image, ImageDraw

from .tooltip import Tooltip

IMAGE_SIZE = 24
BUTTON_SIZE = 34
FLASH_INTERVAL_MS = 1000
RED = '#d02020'
GREY = '#a0a0a0'
BLACK = '#101010'
HOVER = '#d8d8d8'
TOOLTIPS = {
    'record': 'Record',
    'stop': 'Stop',
    'save': 'Save',
    'clear': 'Clear',
}


class State(StrEnum):
    ready = auto()
    recording = auto()
    paused = auto()


class Action(StrEnum):
    record = auto()
    save = auto()
    clear = auto()


class Transport(CTkFrame):
    def __init__(
        self,
        parent: CTkFrame,
        callback: Callable[[State, State, Action], bool],
        hover_time: Callable[[], float],
    ) -> None:
        super().__init__(parent, fg_color='transparent')
        self.callback = callback
        self.hover_time = hover_time
        self._state = State.ready
        self._flash_after: str | None = None
        self._flash_on = False
        self.record_image = _circle(RED)
        self.disabled_stop_image = _square(GREY)
        self.stop_image = _square(BLACK)
        self.pause_image = _pause(RED)
        self.save_image = _save(BLACK)
        self.disabled_save_image = _save(GREY)
        self.clear_image = _cross(BLACK)
        self.disabled_clear_image = _cross(GREY)

        self.record = CTkButton(
            self,
            text='',
            image=self.record_image,
            command=self._on_record,
            width=BUTTON_SIZE,
            height=BUTTON_SIZE,
            fg_color='transparent',
            hover_color=HOVER,
        )
        self.record.pack(side='left')
        self.stop = CTkButton(
            self,
            text='',
            image=self.disabled_stop_image,
            command=self._on_stop,
            width=BUTTON_SIZE,
            height=BUTTON_SIZE,
            fg_color='transparent',
            hover_color=HOVER,
        )
        self.stop.pack(side='left')
        self.save = CTkButton(
            self,
            text='',
            image=self.disabled_save_image,
            command=self._on_save,
            width=BUTTON_SIZE,
            height=BUTTON_SIZE,
            fg_color='transparent',
            hover_color=HOVER,
        )
        self.save.pack(side='left')
        self.clear = CTkButton(
            self,
            text='',
            image=self.disabled_clear_image,
            command=self._on_clear,
            width=BUTTON_SIZE,
            height=BUTTON_SIZE,
            fg_color='transparent',
            hover_color=HOVER,
        )
        self.clear.pack(side='left')
        self._add_tooltips()
        self._configure_buttons()

    @property
    def state(self) -> State:
        return self._state

    def _on_record(self) -> None:
        self._set_state(_record_state(self.state), Action.record)

    def _on_stop(self) -> None:
        self._set_state(_ready_state(self.state), Action.save)

    def _on_save(self) -> None:
        self._set_state(_ready_state(self.state), Action.save)

    def _on_clear(self) -> None:
        self._set_state(_ready_state(self.state), Action.clear)

    def _set_state(self, state: State, action: Action) -> None:
        if state == self.state:
            return
        old_state = self.state
        if not self.callback(old_state, state, action):
            return
        self._state = state
        self._configure_buttons()

    def _configure_buttons(self) -> None:
        if self.state == State.recording:
            self._start_flashing()
        else:
            self._stop_flashing()
            self.record.configure(image=self.record_image)

        ready = self.state == State.ready
        self.stop.configure(
            image=self.disabled_stop_image if ready else self.stop_image,
            state='disabled' if ready else 'normal',
        )
        self.save.configure(
            image=self.disabled_save_image if ready else self.save_image,
            state='disabled' if ready else 'normal',
        )
        self.clear.configure(
            image=self.disabled_clear_image if ready else self.clear_image,
            state='disabled' if ready else 'normal',
        )

    def _start_flashing(self) -> None:
        if self._flash_after is not None:
            return
        self._flash_on = True
        self.record.configure(image=self.pause_image)
        self._flash_after = self.after(FLASH_INTERVAL_MS, self._flash_record)

    def _stop_flashing(self) -> None:
        if self._flash_after is not None:
            self.after_cancel(self._flash_after)
            self._flash_after = None
        self._flash_on = False

    def _flash_record(self) -> None:
        self._flash_after = None
        if self.state != State.recording:
            return
        self._flash_on = not self._flash_on
        image = self.pause_image if self._flash_on else self.record_image
        self.record.configure(image=image)
        self._flash_after = self.after(FLASH_INTERVAL_MS, self._flash_record)

    def _add_tooltips(self) -> None:
        Tooltip(self.record, TOOLTIPS['record'], self.hover_time)
        Tooltip(self.stop, TOOLTIPS['stop'], self.hover_time)
        Tooltip(self.save, TOOLTIPS['save'], self.hover_time)
        Tooltip(self.clear, TOOLTIPS['clear'], self.hover_time)


def _record_state(state: State) -> State:
    return State.paused if state == State.recording else State.recording


def _ready_state(state: State) -> State:
    return State.ready if state != State.ready else state


def _circle(color: str) -> CTkImage:
    image = _blank_image()
    ImageDraw.Draw(image).ellipse((3, 3, 20, 20), fill=color)
    return _ctk_image(image)


def _square(color: str) -> CTkImage:
    image = _blank_image()
    ImageDraw.Draw(image).rectangle((4, 4, 19, 19), fill=color)
    return _ctk_image(image)


def _pause(color: str) -> CTkImage:
    image = _blank_image()
    draw = ImageDraw.Draw(image)
    draw.rectangle((5, 3, 9, 20), fill=color)
    draw.rectangle((14, 3, 18, 20), fill=color)
    return _ctk_image(image)


def _save(color: str) -> CTkImage:
    image = _blank_image()
    draw = ImageDraw.Draw(image)
    draw.rectangle((4, 3, 20, 21), outline=color, width=3)
    draw.rectangle((7, 5, 16, 11), outline=color, width=2)
    draw.rectangle((14, 5, 16, 11), fill=color)
    draw.rectangle((8, 15, 16, 21), outline=color, width=2)
    draw.line((10, 17, 14, 17), fill=color, width=1)
    return _ctk_image(image)


def _cross(color: str) -> CTkImage:
    image = _blank_image()
    draw = ImageDraw.Draw(image)
    draw.line((5, 5, 18, 18), fill=color, width=4)
    draw.line((18, 5, 5, 18), fill=color, width=4)
    return _ctk_image(image)


def _blank_image() -> Image.Image:
    return Image.new('RGBA', (IMAGE_SIZE, IMAGE_SIZE), (0, 0, 0, 0))


def _ctk_image(image: Image.Image) -> CTkImage:
    return CTkImage(light_image=image, dark_image=image, size=(IMAGE_SIZE, IMAGE_SIZE))
