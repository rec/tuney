from pydantic import BaseModel, Field


class AudioDiagnostics(BaseModel):
    callback_statuses: list[str] = Field(default_factory=list)
    callback_errors: list[str] = Field(default_factory=list)
    stream_errors: list[str] = Field(default_factory=list)

    def record_callback_status(self, status: str) -> None:
        self.callback_statuses.append(status)

    def record_callback_error(self, error: str) -> None:
        self.callback_errors.append(error)

    def record_stream_error(self, error: str) -> None:
        self.stream_errors.append(error)

    def take_errors(self) -> list[str]:
        errors: list[str] = []
        while self.stream_errors:
            errors.append(self.stream_errors.pop(0))
        while self.callback_errors:
            errors.append(self.callback_errors.pop(0))
        return errors
