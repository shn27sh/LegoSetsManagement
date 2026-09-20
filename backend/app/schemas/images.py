from pydantic import BaseModel


class ImageUploadResponse(BaseModel):
    image_url: str


class ImageDeleteResponse(BaseModel):
    image_url: str | None
