from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from na_planner.api.schemas import AuditRequest, RecommendRequest
from na_planner.audit import audit
from na_planner.models.audit import AuditResult
from na_planner.models.recommend import Recommendation
from na_planner.programs import list_programs, load_program_by
from na_planner.roadmap import recommend


def create_app() -> FastAPI:
    app = FastAPI(title="NA Course Planner API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
    )

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    @app.get("/programs")
    def programs() -> list[dict]:
        return list_programs()

    @app.post("/audit", response_model=AuditResult)
    def audit_endpoint(req: AuditRequest) -> AuditResult:
        try:
            program = load_program_by(req.program_code, req.catalog_year)
        except KeyError as e:
            raise HTTPException(status_code=404, detail=str(e)) from e
        return audit(req.student, program)

    @app.post("/recommend", response_model=Recommendation)
    def recommend_endpoint(req: RecommendRequest) -> Recommendation:
        try:
            program = load_program_by(req.program_code, req.catalog_year)
        except KeyError as e:
            raise HTTPException(status_code=404, detail=str(e)) from e
        return recommend(req.student, program, req.preferences)

    return app


app = create_app()
