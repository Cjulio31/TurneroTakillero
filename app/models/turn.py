from dataclasses import dataclass


@dataclass
class Turn:
    message_id: str
    terminal_id: str
    turn_number: int
    status: str
    received_at: str
    id: int | None = None
    processed_at: str | None = None
    sent_at: str | None = None
    printed_at: str | None = None
    completed_at: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    ack_status: str | None = None
    acked_at: str | None = None
