from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.shared import figures


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AnswerType(StrEnum):
    expression = "expression"
    numeric = "numeric"
    set = "set"
    interval = "interval"
    matrix = "matrix"
    function = "function"
    multi_part = "multi_part"
    enum = "enum"


class Calculator(StrEnum):
    none = "none"
    scientific = "scientific"
    graphing = "graphing"


class Course(StrEnum):
    prealgebra = "prealgebra"
    algebra1 = "algebra1"
    geometry = "geometry"
    algebra2 = "algebra2"
    precalculus = "precalculus"
    calc1 = "calc1"
    calc2 = "calc2"
    calc3 = "calc3"
    diffeq = "diffeq"
    linalg = "linalg"
    intro_prob_stats = "intro_prob_stats"
    adv_probability = "adv_probability"
    adv_statistics = "adv_statistics"


class DifficultyRange(Strict):
    min: int = Field(ge=1, le=5)
    max: int = Field(ge=1, le=5)

    @field_validator("max")
    @classmethod
    def _ordered(cls, v, info):
        if "min" in info.data and v < info.data["min"]:
            raise ValueError("max must be >= min")
        return v


class Options(Strict):
    include_steps: bool = True
    figure_format: Literal["svg", "spec", "both"] = "both"   # what a problem that needs a figure carries (see Figure)
    word_problems: bool = False
    answer_types: list[AnswerType] | None = None
    exclude_hashes: list[str] = Field(default_factory=list, max_length=500)
    seed: int | None = None
    engine: Literal["llm", "offline"] | None = None   # offline: samplers instead of the model (no API key needed)


class GenerateRequest(Strict):
    course: Course
    topic_ids: list[str] = Field(min_length=1, max_length=10)
    difficulty: int | DifficultyRange = Field(union_mode="left_to_right")
    calculator: Calculator = Calculator.none
    count: int = Field(ge=1, le=20)
    options: Options = Field(default_factory=Options)

    @field_validator("difficulty")
    @classmethod
    def _level(cls, v):
        if isinstance(v, int) and not 1 <= v <= 5:
            raise ValueError("difficulty must be 1-5")
        return v

    @property
    def level_range(self) -> tuple[int, int]:
        d = self.difficulty
        return (d, d) if isinstance(d, int) else (d.min, d.max)


class Answer(BaseModel):
    type: AnswerType
    latex: str
    sympy: str | None = None
    numeric: float | None = None
    precision: int | None = None


class Step(BaseModel):
    n: int
    text: str
    latex: str | None = None
    sympy: str | None = None
    verified: bool


class Figure(BaseModel):
    """`content` is an SVG string and `spec` the same drawing as data (sampled points, ticks, markers; app/shared/figures.py), so
    a client with its own plotter can draw it. Which of the two is present follows options.figure_format."""
    format: Literal["svg", "spec", "both"] = "both"
    content: str | None = None
    spec: dict | None = None
    alt: str


class DifficultyFeatures(BaseModel):
    version: str
    raw: dict
    axes: dict[str, float]
    score: float
    level: int


class Verification(BaseModel):
    status: Literal["passed"]
    method: str
    attempts: int
    calculator_check: Literal["passed", "n/a"]


class Problem(BaseModel):
    id: str
    hash: str
    topic_id: str
    difficulty: int
    calculator: Calculator
    statement: str
    answer: Answer
    steps: list[Step] = Field(default_factory=list)
    requires_figure: bool = False       # the problem cannot be answered without its figure; the figure is then present
    figure: Figure | None = None
    difficulty_features: DifficultyFeatures | None = None
    verification: Verification


class Shortfall(BaseModel):
    requested: int
    returned: int
    reason: Literal["retry_cap_reached", "timeout", "verification_failed"]


class Meta(BaseModel):
    model: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0
    cost_usd: float = 0.0


class GenerateResponse(BaseModel):
    generation_id: str
    request: GenerateRequest
    problems: list[Problem]
    shortfall: Shortfall | None
    meta: Meta


DEBUG_FIELDS = {"difficulty_features"}


def public_problem(p: Problem, debug: bool) -> dict:
    """Serialize one problem, dropping debug-only fields unless debug is on."""
    data = p.model_dump(mode="json")
    if not debug:
        for f in DEBUG_FIELDS:
            data.pop(f, None)
        data["answer"].pop("sympy", None)
        for s in data["steps"]:
            s.pop("sympy", None)
        fig = data.get("figure")
        if fig and fig.get("spec"):          # the exact formula of a graph-only problem would give the answer away
            fig["spec"] = figures.public_spec(fig["spec"], debug=False)
    return data


def public_dump(resp: GenerateResponse, debug: bool) -> dict:
    data = resp.model_dump(mode="json", exclude={"problems"})
    data["problems"] = [public_problem(p, debug) for p in resp.problems]
    return data
