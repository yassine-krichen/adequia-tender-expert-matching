from pydantic import BaseModel


class TdrUploadAck(BaseModel):
    """POST /tdrs response — extraction runs on the worker, not the request.

    See app/worker/tasks.py and GET /tdrs/{tdr_id}/status for the polling
    contract the frontend uses to find out when tdr_id is ready.
    """

    tdr_id: str
    status: str


class TdrStatus(BaseModel):
    """GET /tdrs/{tdr_id}/status response.

    step/chunks_done/chunks_total are only populated while status is
    "processing" — they come from the worker's Redis progress hash, which
    expires once the job finishes (see app/worker/tasks.py).
    """

    tdr_id: str
    status: str
    step: str | None = None
    chunks_done: int | None = None
    chunks_total: int | None = None
    error_message: str | None = None
