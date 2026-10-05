from pydantic import BaseModel


class MigrationStatusResponse(BaseModel):
    rp_client_id: str
    completed: bool
