import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.database import engine
from app.routers import auth, customer, organizer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    yield
    await engine.dispose()


app = FastAPI(
    title="Event Booking System",
    version="1.0.0",
    description="Backend APIs for event organizers and customers.",
    lifespan=lifespan,
)

app.include_router(auth.router)
app.include_router(organizer.router)
app.include_router(customer.router)


@app.get("/health", tags=["health"])
async def health() -> dict:
    return {"status": "ok"}
