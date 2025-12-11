from typing import Dict

from app.utils.schemas import ResponseModel
from fastapi.responses import JSONResponse


def generate_error_response(status_code: int, message: str):
    return JSONResponse(
        content=ResponseModel(
            success=False,
            message=message,
        ).model_dump(),
        status_code=status_code,
    )


def format_error_response(json: Dict):
    message_id = json.get("messageId", "Unknown error")
    message_description = json.get("messageDescription", "Unknown error")
    return f"{message_id} - {message_description}"


def string_error_response(message: str = None, description: str = None) -> str:
    if not message:
        message = "Unknown error"
    if not description:
        description = ""
    return f"{message} - {description}"
