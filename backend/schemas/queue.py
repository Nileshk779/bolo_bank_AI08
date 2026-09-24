from pydantic import BaseModel


class TokenRequest(BaseModel):
    customer_name: str
    service_type: str
    customer_type: str = "general"  # general | elderly | rural
