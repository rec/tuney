from collections.abc import Callable
from enum import StrEnum, auto
from typing import Any

from customtkinter import CTkButton, CTkFrame, CTkImage
from PIL import Image, ImageDraw

IMAGE_SIZE = 24
BUTTON_SIZE = 34
RED = '#d02020'
GREY = '#a0a0a0'
BLACK = '#101010'


class State(StrEnum):
    ready = auto()
    recording = auto()
    paused = auto()


class Transport(CTkFrame):
    def __init__(
        self,
        parent: CTkFrame,
        callback: Callable[[State], Any],
    ) -> None:
        super().__init__(parent, fg_color='transparent')
        self.callback = callback
        self._state = State.ready
        self.record_image = _circle(RED)
        self.disabled_stop_image = _square(GREY)
        self.stop_image = _square(BLACK)
        self.pause_image = _pause(RED)

        self.record = CTkButton(
            self,
            text='',
            image=self.record_image,
            command=self._on_record,
            width=BUTTON_SIZE,
            height=BUTTON_SIZE,
            fg_color='transparent',
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
        )
        self.stop.pack(side='left')
        self._configure_buttons()

    @property
    def state(self) -> State:
        return self._state

    def _on_record(self) -> None:
        self._set_state(_record_state(self.state))

    def _on_stop(self) -> None:
        self._set_state(_stop_state(self.state))

    def _set_state(self, state: State) -> None:
        if state == self.state:
            return
        self._state = state
        self._configure_buttons()
        self.callback(state)

    def _configure_buttons(self) -> None:
        if self.state == State.recording:
            self.record.configure(image=self.pause_image)
        else:
            self.record.configure(image=self.record_image)

        ready = self.state == State.ready
        self.stop.configure(
            image=self.disabled_stop_image if ready else self.stop_image,
            state='disabled' if ready else 'normal',
        )


def _record_state(state: State) -> State:
    return State.paused if state == State.recording else State.recording


def _stop_state(state: State) -> State:
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


def _blank_image() -> Image.Image:
    return Image.new('RGBA', (IMAGE_SIZE, IMAGE_SIZE), (0, 0, 0, 0))


def _ctk_image(image: Image.Image) -> CTkImage:
    return CTkImage(light_image=image, dark_image=image, size=(IMAGE_SIZE, IMAGE_SIZE))
