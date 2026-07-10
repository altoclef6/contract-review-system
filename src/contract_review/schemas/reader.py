from pydantic import BaseModel


class TextLocation(BaseModel):
    page: int
    x0: float
    y0: float
    x1: float
    y1: float
    text: str


class TextLocationResult(BaseModel):
    review_id: str
    query: str
    locations: list[TextLocation]
