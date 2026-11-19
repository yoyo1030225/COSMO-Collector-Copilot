r"""啟動：.venv\Scripts\python.exe -m uvicorn api:app --host 127.0.0.1 --port 8000。"""

from uuid import UUID

from fastapi import BackgroundTasks, FastAPI, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator

from collection_jobs import CollectionBusyError, CollectionJobs


class NicknameRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    nickname: str = Field(min_length=1, max_length=64)

    @field_validator("nickname", mode="before")
    @classmethod
    def normalize(cls, value):
        if isinstance(value, str):
            value = value.strip().removeprefix("@")
            if any(ord(character) < 32 or ord(character) == 127 for character in value):
                raise ValueError("暱稱不能包含控制字元。")
        return value


def create_app(jobs: CollectionJobs | None = None) -> FastAPI:
    service = jobs if jobs is not None else CollectionJobs()
    app = FastAPI(title="COSMO Collector API", version="0.1.0")

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/collections/latest")
    def latest(response: Response):
        response.headers["Cache-Control"] = "no-store"
        try:
            return service.latest()
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="尚無成功查詢的收藏。") from None

    @app.post("/collections/sync", status_code=202)
    def start(request: NicknameRequest, background_tasks: BackgroundTasks, response: Response):
        response.headers["Cache-Control"] = "no-store"
        try:
            job, created = service.create(request.nickname)
        except CollectionBusyError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        if created:
            background_tasks.add_task(service.run, job["job_id"])
        return job

    @app.get("/collections/jobs/{job_id}")
    def progress(job_id: UUID, response: Response):
        response.headers["Cache-Control"] = "no-store"
        try:
            return service.get(job_id.hex)
        except KeyError:
            raise HTTPException(status_code=404, detail="查詢已不存在，請重新讀取收藏。") from None

    return app


app = create_app()
