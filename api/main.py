from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from dotenv import load_dotenv
from routers.journal_router import router as journal_router
import logging
import sys
from contextlib import asynccontextmanager

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("journal")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("LearningSteps API started")
    yield
    logger.info("LearningSteps API stopped")

app = FastAPI(title="LearningSteps API", description="A simple learning journal API for tracking daily work, struggles, and intentions", lifespan=lifespan)
app.include_router(journal_router)


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/docs")
