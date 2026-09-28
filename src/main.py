from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.http.equipments import router as equipments
from src.http.loans import router as loans
from src.http.users import router as users

app = FastAPI(debug=True)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(users)
app.include_router(equipments)
app.include_router(loans)
