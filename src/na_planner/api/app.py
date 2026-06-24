from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from na_planner.api.export import plan_to_json, plan_to_pdf
from na_planner.api.schemas import AuditRequest, ParseTextRequest, RecommendRequest
from na_planner.audit import audit
from na_planner.exam_credit import merge_exam_credit
from na_planner.exam_credit_loader import load_chart_for
from na_planner.ingestion.build import to_student_record
from na_planner.ingestion.models import NoTextLayerError
from na_planner.ingestion.pdf import parse_transcript_pdf
from na_planner.ingestion.transcript_text import parse_transcript_text
from na_planner.models.audit import AuditResult
from na_planner.models.exam_credit import ExamCreditChart, ExamResolution
from na_planner.models.recommend import Recommendation
from na_planner.models.student import StudentRecord
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

    @app.get("/programs/{code}/courses")
    def program_courses(code: str, catalog_year: int = 2026) -> list[dict]:
        # Catalog course codes + titles for the structured transfer-credit dropdown.
        try:
            program = load_program_by(code, catalog_year)
        except KeyError as e:
            raise HTTPException(status_code=404, detail=str(e)) from e
        return [
            {"code": c.code, "title": c.title}
            for c in sorted(program.courses.values(), key=lambda c: c.code)
        ]

    @app.get("/exam-chart", response_model=ExamCreditChart)
    def exam_chart(catalog_year: int = 2026) -> ExamCreditChart:
        try:
            return load_chart_for(catalog_year)
        except KeyError as e:
            raise HTTPException(status_code=404, detail=str(e)) from e

    @app.post("/resolve-exams", response_model=ExamResolution)
    def resolve_exams_endpoint(req: AuditRequest) -> ExamResolution:
        # Authoritative resolution preview: applies the cross-exam cap/dedup rules the
        # per-row client preview cannot, and returns diagnostics for the UI to show.
        try:
            chart = load_chart_for(req.catalog_year)
        except KeyError as e:
            raise HTTPException(status_code=404, detail=str(e)) from e
        _, resolution = merge_exam_credit(req.student, chart)
        return resolution

    def _with_exam_credit(student: StudentRecord, catalog_year: int) -> StudentRecord:
        # Resolve reported exams into external credit before the engine runs. Absence
        # of a chart for the catalog year leaves exams unresolved rather than failing.
        if not student.exams:
            return student
        try:
            chart = load_chart_for(catalog_year)
        except KeyError:
            return student
        merged, _ = merge_exam_credit(student, chart)
        return merged

    @app.post("/audit", response_model=AuditResult)
    def audit_endpoint(req: AuditRequest) -> AuditResult:
        try:
            program = load_program_by(req.program_code, req.catalog_year)
        except KeyError as e:
            raise HTTPException(status_code=404, detail=str(e)) from e
        student = _with_exam_credit(req.student, req.catalog_year)
        return audit(student, program)

    @app.post("/recommend", response_model=Recommendation)
    def recommend_endpoint(req: RecommendRequest) -> Recommendation:
        try:
            program = load_program_by(req.program_code, req.catalog_year)
        except KeyError as e:
            raise HTTPException(status_code=404, detail=str(e)) from e
        student = _with_exam_credit(req.student, req.catalog_year)
        return recommend(student, program, req.preferences)

    @app.post("/parse/text", response_model=StudentRecord)
    def parse_text(req: ParseTextRequest) -> StudentRecord:
        parsed = parse_transcript_text(req.text)
        return to_student_record(parsed, req.program_code, req.catalog_year)

    @app.post("/parse/pdf", response_model=StudentRecord)
    def parse_pdf(
        file: UploadFile = File(...),  # noqa: B008
        program_code: str = Form(...),  # noqa: B008
        catalog_year: int = Form(...),  # noqa: B008
    ) -> StudentRecord:
        data = file.file.read()
        try:
            parsed = parse_transcript_pdf(data)
        except NoTextLayerError as e:
            raise HTTPException(status_code=422, detail=str(e)) from e
        return to_student_record(parsed, program_code, catalog_year)

    @app.post("/export/json")
    def export_json(rec: Recommendation) -> Response:
        return Response(
            content=plan_to_json(rec), media_type="application/json",
            headers={"content-disposition": "attachment; filename=plan.json"},
        )

    @app.post("/export/pdf")
    def export_pdf(rec: Recommendation) -> Response:
        return Response(
            content=plan_to_pdf(rec), media_type="application/pdf",
            headers={"content-disposition": "attachment; filename=plan.pdf"},
        )

    static_dir = Path(__file__).parent.parent / "static"

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return (static_dir / "index.html").read_text(encoding="utf-8")

    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    return app


app = create_app()
