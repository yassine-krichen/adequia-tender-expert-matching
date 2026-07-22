from datetime import datetime

from pydantic import BaseModel


class TdrSummary(BaseModel):
    """GET /tdrs response shape -- the past-TDRs list, not a full extraction
    dump. Mirrors CandidateSummary in the candidates feature.
    """

    tdr_id: str
    mission_title: str | None
    status: str
    created_at: datetime


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


class MatchingStatus(BaseModel):
    """GET /tdrs/{tdr_id}/match-status response.

    Mirrors TdrStatus's shape for the matching run instead of extraction —
    comes from the worker's Redis progress hash (see
    app/worker/matching_tasks.py), which expires once the run finishes.
    "not_started" means POST /tdrs/{tdr_id}/match hasn't been called yet
    (no Redis key exists).
    """

    tdr_id: str
    status: str  # "not_started" | "processing" | "done" | "failed"
    positions_done: int | None = None
    positions_total: int | None = None
