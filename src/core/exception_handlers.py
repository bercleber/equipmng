import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from src.services.exceptions import InvalidLoanStateError, LoanEquipmentUnavailableError

logger = logging.getLogger(__name__)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(InvalidLoanStateError)
    @app.exception_handler(LoanEquipmentUnavailableError)
    async def loan_conflict(request: Request, err: Exception) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(err)})

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, err: Exception) -> JSONResponse:
        logger.error(
            "Unhandled error during %s %s", request.method, request.url.path,
            exc_info=(type(err), err, err.__traceback__),
        )
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})
