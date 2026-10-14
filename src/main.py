from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.core.exception_handlers import register_exception_handlers
from src.core.settings import get_settings
from src.http.auth import router as auth
from src.http.equipments import router as equipments
from src.http.loans import router as loans
from src.http.users import router as users

app = FastAPI(debug=False)
register_exception_handlers(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(users)
app.include_router(auth)
app.include_router(equipments)
app.include_router(loans)
