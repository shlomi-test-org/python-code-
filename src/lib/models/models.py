from pydantic import BaseModel


class PrJitEventWatchdogEvent(BaseModel):
    gsi_bucket_index: int
