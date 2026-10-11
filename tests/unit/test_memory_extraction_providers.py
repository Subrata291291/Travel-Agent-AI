import pytest
from pydantic import ValidationError

from app.config.settings import settings
from app.config.settings import Settings
from app.database.models import Tenant, UserMemory, UserMemoryEmbedding
from app.llm.router import LLMRouter
from app.memory.long_term import LongTermMemory, MemoryCandidate, MemoryExtraction
from app.memory.vector_index import MemoryVectorIndex


MESSAGE = "I prefer travelling by train."
CANDIDATE = {
    "text": "Prefers travelling by train",
    "topic": "transport",
    "kind": "semantic",
    "importance": 0.8,
    "confidence": 0.95,
    "source_quote": MESSAGE,
}


class FakeEmbedder:
    model = "test-embedder"
    dimensions = 2

    def embed(self, _text):
        return [1.0, 0.0]


def _owner(db):
    db.add(Tenant(tenant_id="tenant-a", name="Test", slug="tenant-a", status="active"))
    db.commit()


class FakeStructured:
    def __init__(self, output=None, error=None, on_invoke=None):
        self.output = output
        self.error = error
        self.on_invoke = on_invoke

    def invoke(self, prompt):
        if self.on_invoke:
            self.on_invoke(prompt)
        if self.error:
            raise self.error
        return self.output


class FakeLLM:
    def __init__(self, structured):
        self.structured = structured
        self.method = None

    def with_structured_output(self, schema, method):
        assert schema is MemoryExtraction
        self.method = method
        return self.structured


def test_groq_json_mode_prompt_contains_json_and_falls_back(monkeypatch):
    router = LLMRouter()
    router.provider_order = ["groq", "openrouter"]
    observed = []
    groq = FakeLLM(FakeStructured(error=RuntimeError("json required"), on_invoke=observed.append))
    openrouter = FakeLLM(FakeStructured(output={"memories": [CANDIDATE]}))
    monkeypatch.setattr(router, "get_llm", lambda name: {"groq": groq, "openrouter": openrouter}[name])

    result = router.invoke_structured("Extract a stable preference.", MemoryExtraction)

    assert "json" in observed[0].casefold()
    assert groq.method == "json_mode"
    assert isinstance(result, MemoryExtraction)
    assert result.memories[0].text == CANDIDATE["text"]


def test_openrouter_bare_candidate_list_is_validated_against_extraction_contract():
    extracted = MemoryExtraction.model_validate([CANDIDATE])
    assert len(extracted.memories) == 1
    assert extracted.memories[0] == MemoryCandidate.model_validate(CANDIDATE)

    with pytest.raises(ValidationError):
        MemoryExtraction.model_validate([{"text": "partial"}])
    with pytest.raises(ValidationError):
        MemoryExtraction.model_validate([CANDIDATE] * 6)


def test_invalid_provider_output_falls_back_instead_of_reporting_success(monkeypatch):
    router = LLMRouter()
    router.provider_order = ["openrouter", "gemini"]
    attempted = []
    bad = FakeLLM(FakeStructured(output={"unexpected": "shape"}, on_invoke=lambda _p: attempted.append("bad")))
    good = FakeLLM(FakeStructured(output=[CANDIDATE], on_invoke=lambda _p: attempted.append("good")))
    monkeypatch.setattr(router, "get_llm", lambda name: {"openrouter": bad, "gemini": good}[name])

    result = router.invoke_structured("Extract JSON.", MemoryExtraction)

    assert attempted == ["bad", "good"]
    assert result.memories[0].source_quote == MESSAGE


def test_openai_quota_error_falls_back_without_logging_prompt(monkeypatch, caplog):
    class QuotaError(Exception):
        status_code = 429

    private_prompt = f"Extract JSON from private text: {MESSAGE}"
    router = LLMRouter()
    router.provider_order = ["openai", "gemini"]
    openai = FakeLLM(FakeStructured(error=QuotaError("insufficient_quota")))
    gemini = FakeLLM(FakeStructured(output={"memories": [CANDIDATE]}))
    monkeypatch.setattr(router, "get_llm", lambda name: {"openai": openai, "gemini": gemini}[name])

    result = router.invoke_structured(private_prompt, MemoryExtraction)

    assert result.memories
    assert "insufficient_quota" not in caplog.text
    assert MESSAGE not in caplog.text


def test_gemini_model_is_configurable_and_passed_to_compatible_sdk(monkeypatch):
    import app.llm.gemini as gemini_module

    monkeypatch.setattr(settings, "google_api_key", "test-key")
    monkeypatch.setattr(settings, "gemini_model", "gemini-3.8-flash")

    provider = gemini_module.GeminiProvider()
    llm = provider.get_llm()

    assert llm.model == "gemini-3.8-flash"
    # Constructing this runnable validates compatibility with the installed
    # langchain-google-genai SDK without making a paid API request.
    assert llm.with_structured_output(MemoryExtraction, method="json_mode") is not None


def test_gemini_model_reads_environment_override(monkeypatch):
    monkeypatch.setenv("GEMINI_MODEL", "gemini-configured-model")
    configured = Settings(jwt_secret_key="test-secret", _env_file=None)
    assert configured.gemini_model == "gemini-configured-model"


def test_bare_list_extraction_commits_relational_memory_before_embedding(test_db):
    _owner(test_db)

    class ListProvider:
        def invoke_structured(self, _prompt, _schema):
            return [CANDIDATE]

    class CommitCheckingIndex(MemoryVectorIndex):
        def index_memory(self, db, memory, force=False):
            from sqlalchemy.orm import Session
            with Session(db.get_bind()) as verify_db:
                assert verify_db.get(UserMemory, memory.memory_id) is not None
            return super().index_memory(db, memory, force)

    index = CommitCheckingIndex(FakeEmbedder())
    service = LongTermMemory(ListProvider(), index)
    assert service.extract_and_store(test_db, "user-a", "tenant-a", MESSAGE) == 1

    # A separate session sees the committed relational memory and its vector.
    from sqlalchemy import select
    from sqlalchemy.orm import Session
    with Session(test_db.get_bind()) as verify_db:
        saved = verify_db.scalar(select(UserMemory).where(UserMemory.user_id == "user-a"))
        assert saved is not None
        assert saved.text == CANDIDATE["text"]
        vector = verify_db.get(UserMemoryEmbedding, saved.memory_id)
        assert vector is not None
