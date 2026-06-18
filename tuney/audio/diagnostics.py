from pydantic import BaseModel, Field


class AudioDiagnostics(BaseModel):
    callback_statuses: list[str] = Field(default_factory=list)
    stream_errors: list[str] = Field(default_factory=list)

    def record_callback_status(self, status: str) -> None:
        self.callback_statuses.append(status)

    def record_stream_error(self, error: str) -> None:
        self.stream_errors.append(error)
