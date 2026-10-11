import uuid
from typing import Any, Dict, List, Optional
import pytest
from app.knowledge.schemas import ChunkMetadata, KnowledgeChunk, SourceType
from app.safety.enums import RecommendedAction, SafetyState
from app.safety.output_validator import validate_response_safety
from app.schemas.orchestrator import OrchestrationRequest, SourceProvenance
from app.services.conversation_orchestrator import (
    DEFAULT_CRISIS_SAFETY_RESPONSE,
    GENERATOR_ERROR_FALLBACK,
    SAFE_FALLBACK_RESPONSE,
    ConversationOrchestrator,
    DeterministicFakeResponseGenerator,
)


class FakeRetrievalService:
    """Deterministic fake retrieval service for unit testing."""

    def __init__(
        self,
        chunks: Optional[List[Dict[str, Any]]] = None,
        should_fail: bool = False,
        failure_exception: Optional[Exception] = None,
    ) -> None:
        self.chunks = chunks if chunks is not None else []
        self.should_fail = should_fail
        self.failure_exception = failure_exception or RuntimeError("Simulated Qdrant connection error")
        self.calls: List[Dict[str, Any]] = []

    async def retrieve_relevant_chunks(
        self,
        query: str,
        top_k: int = 5,
        score_threshold: float = 0.0,
    ) -> List[Dict[str, Any]]:
        self.calls.append({
            "query_len": len(query),
            "top_k": top_k,
            "score_threshold": score_threshold,
        })
        if self.should_fail:
            raise self.failure_exception
        return self.chunks[:top_k]


@pytest.fixture
def sample_chunk() -> KnowledgeChunk:
    metadata = ChunkMetadata(
        source_type=SourceType.EDUCATIONAL_RESOURCE,
        publisher="National Institute of Mental Health",
        version="1.0",
        reviewed=True,
        total_chunks=1,
        start_char=0,
        end_char=100,
    )
    return KnowledgeChunk(
        chunk_id="doc-stress-01_c000",
        document_id="doc-stress-01",
        chunk_index=0,
        text="Deep diaphragmatic breathing stimulates the parasympathetic nervous system.",
        title="Mindful Breathing Guide",
        source_name="NIMH Educational Resources",
        source_url="https://example.org/mindful-breathing",
        topic="stress_management",
        language="en",
        metadata=metadata,
    )


# -----------------------------------------------------------------------------
# Test Cases
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_low_risk_message_follows_normal_pipeline(sample_chunk: KnowledgeChunk):
    """Test low-risk message executes safety pre-check, retrieves knowledge, generates dialogue,
    and returns source provenance.
    """
    retrieval_service = FakeRetrievalService(
        chunks=[{"chunk": sample_chunk, "score": 0.89, "payload": {}}]
    )
    fake_generator = DeterministicFakeResponseGenerator()
    orchestrator = ConversationOrchestrator(
        retrieval_service=retrieval_service,
        response_generator=fake_generator,
    )

    request = OrchestrationRequest(
        message="I have been feeling stressed about my work presentations lately.",
        conversation_id=uuid.uuid4(),
    )

    response = await orchestrator.handle_turn(request)

    assert response.is_safety_diverted is False
    assert response.fallback_triggered is False
    assert response.fallback_reason is None
    assert response.safety_result.state == SafetyState.LOW
    assert response.safety_result.recommended_action == RecommendedAction.NORMAL_CONVERSATION

    # Verification of provenance
    assert len(response.sources) == 1
    source = response.sources[0]
    assert source.document_id == "doc-stress-01"
    assert source.chunk_id == "doc-stress-01_c000"
    assert source.title == "Mindful Breathing Guide"
    assert source.source_name == "NIMH Educational Resources"
    assert source.score == 0.89

    # Both retrieval and generation must be invoked
    assert len(retrieval_service.calls) == 1
    assert len(fake_generator.calls) == 1
    assert "Mindful Breathing Guide" in response.response_text


@pytest.mark.asyncio
async def test_high_risk_message_bypasses_retrieval_and_generation():
    """Test acute high-risk message immediately halts normal pipeline, bypassing both
    retrieval and response generation, and returning nonjudgmental crisis guidance.
    """
    retrieval_service = FakeRetrievalService()
    fake_generator = DeterministicFakeResponseGenerator()
    orchestrator = ConversationOrchestrator(
        retrieval_service=retrieval_service,
        response_generator=fake_generator,
    )

    request = OrchestrationRequest(
        message="I want to kill myself tonight, I can't take this anymore.",
        conversation_id=uuid.uuid4(),
    )

    response = await orchestrator.handle_turn(request)

    assert response.is_safety_diverted is True
    assert response.fallback_triggered is False
    assert response.safety_result.state == SafetyState.HIGH_RISK
    assert response.safety_result.recommended_action == RecommendedAction.IMMEDIATE_HUMAN_EMERGENCY_SUPPORT
    assert response.sources == []

    # MUST bypass ordinary generation and retrieval
    assert len(retrieval_service.calls) == 0
    assert len(fake_generator.calls) == 0

    # Must provide immediate crisis contact resources
    assert "988" in response.response_text
    assert "741741" in response.response_text
    assert "emergency" in response.response_text.lower()


@pytest.mark.asyncio
async def test_retrieval_failure_handled_safely_no_fabricated_sources():
    """Test retrieval failures (e.g. Qdrant down) are caught safely without fabricating
    sources or throwing unhandled exceptions.
    """
    failing_retrieval = FakeRetrievalService(should_fail=True)
    fake_generator = DeterministicFakeResponseGenerator()
    orchestrator = ConversationOrchestrator(
        retrieval_service=failing_retrieval,
        response_generator=fake_generator,
    )

    request = OrchestrationRequest(
        message="Can you suggest some general relaxation strategies?",
    )

    response = await orchestrator.handle_turn(request)

    assert response.is_safety_diverted is False
    assert response.fallback_triggered is False
    # No sources fabricated
    assert response.sources == []
    # Generator was still called with empty chunks
    assert len(fake_generator.calls) == 1
    assert fake_generator.calls[0]["chunks_count"] == 0
    assert "coping strategies" in response.response_text.lower()


@pytest.mark.asyncio
async def test_generator_failure_returns_safe_error_response():
    """Test generator technical failure (e.g. timeout) returns a safe fallback message."""
    failing_generator = DeterministicFakeResponseGenerator(should_fail=True)
    orchestrator = ConversationOrchestrator(
        response_generator=failing_generator,
    )

    request = OrchestrationRequest(
        message="I'm feeling a little anxious.",
    )

    response = await orchestrator.handle_turn(request)

    assert response.fallback_triggered is True
    assert response.fallback_reason == "GENERATOR_ERROR"
    assert response.is_safety_diverted is False
    assert response.sources == []
    assert response.response_text == GENERATOR_ERROR_FALLBACK


@pytest.mark.asyncio
async def test_unsafe_generated_response_blocked_by_final_validation():
    """Test final response safety validation intercepts high-risk output generated by LLM."""
    unsafe_generator = DeterministicFakeResponseGenerator(
        canned_response="Here are instructions on how to end my life and commit suicide."
    )
    orchestrator = ConversationOrchestrator(
        response_generator=unsafe_generator,
    )

    request = OrchestrationRequest(
        message="What can I do when I am stressed?",
    )

    response = await orchestrator.handle_turn(request)

    assert response.fallback_triggered is True
    assert response.fallback_reason == "UNSAFE_OUTPUT_BLOCKED"
    assert response.response_text == SAFE_FALLBACK_RESPONSE
    # The unsafe output text must NOT be returned
    assert "suicide" not in response.response_text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "medication_response",
    [
        "You should start taking 20mg of Prozac every morning.",
        "I recommend you stop taking your medication right away.",
        "You need to increase your dosage of Zoloft.",
        "Take 2 pills of Xanax whenever you feel anxious.",
        "I advise you to change your medication regimen.",
        "You should discontinue your antidepressant medication.",
    ],
)
async def test_medication_advice_blocked_by_final_validation(medication_response: str):
    """Test system strictly enforces non-prescriptive boundary and blocks medication advice."""
    prescriptive_generator = DeterministicFakeResponseGenerator(
        canned_response=medication_response
    )
    orchestrator = ConversationOrchestrator(
        response_generator=prescriptive_generator,
    )

    request = OrchestrationRequest(
        message="Should I change how I take my medicine?",
    )

    response = await orchestrator.handle_turn(request)

    assert response.fallback_triggered is True
    assert response.fallback_reason == "UNSAFE_OUTPUT_BLOCKED"
    assert response.response_text == SAFE_FALLBACK_RESPONSE
    # Unsafe prescriptive text must never leak to user
    assert medication_response not in response.response_text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "diagnostic_response",
    [
        "Based on your symptoms, I diagnose you with major depression.",
        "You definitely have bipolar disorder.",
        "You meet the diagnostic criteria for generalized anxiety disorder.",
        "I believe you have clinical depression.",
        "My diagnosis is that you have schizophrenia.",
    ],
)
async def test_diagnostic_claim_blocked_by_final_validation(diagnostic_response: str):
    """Test system strictly enforces non-diagnostic boundary and blocks diagnostic claims."""
    diagnostic_generator = DeterministicFakeResponseGenerator(
        canned_response=diagnostic_response
    )
    orchestrator = ConversationOrchestrator(
        response_generator=diagnostic_generator,
    )

    request = OrchestrationRequest(
        message="Do you think I have depression?",
    )

    response = await orchestrator.handle_turn(request)

    assert response.fallback_triggered is True
    assert response.fallback_reason == "UNSAFE_OUTPUT_BLOCKED"
    assert response.response_text == SAFE_FALLBACK_RESPONSE
    # Diagnostic statement must never leak to user
    assert diagnostic_response not in response.response_text


@pytest.mark.asyncio
async def test_non_prescriptive_educational_response_passes_validation():
    """Test benign psychoeducational response with appropriate disclaimers passes validation cleanly."""
    valid_text = (
        "Grounding exercises such as the 5-4-3-2-1 technique can help bring attention back to the present. "
        "Please note this is psychoeducational information and not a medical diagnosis. "
        "Consult a healthcare professional for clinical advice."
    )
    benign_generator = DeterministicFakeResponseGenerator(canned_response=valid_text)
    orchestrator = ConversationOrchestrator(response_generator=benign_generator)

    request = OrchestrationRequest(
        message="What is a grounding technique?",
    )

    response = await orchestrator.handle_turn(request)

    assert response.fallback_triggered is False
    assert response.is_safety_diverted is False
    assert response.response_text == valid_text


@pytest.mark.asyncio
async def test_concern_state_routes_supportively_without_crisis_bypass():
    """Test CONCERN state messages (e.g. hopelessness) trigger supportive check-in context
    without bypassing knowledge retrieval or response generation.
    """
    retrieval_service = FakeRetrievalService()
    fake_generator = DeterministicFakeResponseGenerator()
    orchestrator = ConversationOrchestrator(
        retrieval_service=retrieval_service,
        response_generator=fake_generator,
    )

    request = OrchestrationRequest(
        message="I feel completely hopeless and nothing seems to matter anymore.",
    )

    response = await orchestrator.handle_turn(request)

    assert response.safety_result.state == SafetyState.CONCERN
    assert response.safety_result.recommended_action == RecommendedAction.SUPPORTIVE_CHECK_IN
    # CONCERN is not acute high-risk; does not divert to emergency bypass
    assert response.is_safety_diverted is False
    assert response.fallback_triggered is False
    assert len(fake_generator.calls) == 1
    assert fake_generator.calls[0]["context"]["safety_state"] == "CONCERN"
    assert fake_generator.calls[0]["context"]["recommended_action"] == "SUPPORTIVE_CHECK_IN"


def test_empty_or_whitespace_message_rejected():
    """Test OrchestrationRequest validates non-empty and non-whitespace message content."""
    with pytest.raises(ValueError):
        OrchestrationRequest(message="")

    with pytest.raises(ValueError):
        OrchestrationRequest(message="   \n\t  ")


@pytest.mark.asyncio
async def test_provenance_handles_dict_payload():
    """Test provenance extraction supports raw dictionary items in retrieval results."""
    dict_chunk = {
        "chunk": {
            "document_id": "doc-dict-99",
            "chunk_id": "doc-dict-99_c01",
            "title": "Sleep Hygiene Guidelines",
            "source_name": "Public Sleep Institute",
            "source_url": "https://example.org/sleep",
            "topic": "sleep",
        },
        "score": 0.82,
    }
    retrieval_service = FakeRetrievalService(chunks=[dict_chunk])
    orchestrator = ConversationOrchestrator(retrieval_service=retrieval_service)

    request = OrchestrationRequest(message="How can I improve sleep?")
    response = await orchestrator.handle_turn(request)

    assert len(response.sources) == 1
    assert response.sources[0].document_id == "doc-dict-99"
    assert response.sources[0].title == "Sleep Hygiene Guidelines"
    assert response.sources[0].score == 0.82


def test_output_validator_direct_evaluation():
    """Direct unit tests for validate_response_safety function."""
    # Empty
    assert validate_response_safety("").is_safe is False
    assert validate_response_safety("   ").is_safe is False

    # High risk
    assert validate_response_safety("Here is how to commit suicide.").is_safe is False

    # Diagnostic
    assert validate_response_safety("I diagnose you with depression.").is_safe is False
    assert validate_response_safety("You definitely have schizophrenia.").is_safe is False

    # Prescriptive
    assert validate_response_safety("You should stop taking your medication.").is_safe is False
    assert validate_response_safety("I can prescribe you Prozac.").is_safe is False

    # Safe educational
    assert validate_response_safety("Deep breathing helps lower stress.").is_safe is True
