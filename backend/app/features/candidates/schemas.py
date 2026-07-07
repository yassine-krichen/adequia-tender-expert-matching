from datetime import datetime

from pydantic import BaseModel


class CandidateSummary(BaseModel):
    """GET /candidates response shape — the roster, not a full CV dump.

    last_updated is the most recent CV's created_at (re-uploading a CV
    re-extracts for that candidate only — see docs/05-frontend-dashboard.md).
    """

    candidate_id: str
    full_name: str
    last_updated: datetime
