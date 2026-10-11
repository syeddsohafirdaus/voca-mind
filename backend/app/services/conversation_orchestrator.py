from typing import Any, Dict, List, Optional, Protocol, runtime_checkable
from app.knowledge.schemas import KnowledgeChunk
from app.logger import logger
from app.safety.engine import evaluate_message
from app.safety.enums import RecommendedAction, SafetyState
from app.safety.output_validator import validate_response_safety
from app.safety.schemas import SafetyResult
from app.schemas.orchestrator import (
    OrchestrationRequest,
    OrchestrationResponse,
    SourceProvenance,
)

# Standardized safety and fallback responses
DEFAULT_CRISIS_SAFETY_RESPONSE = (
    "I hear how much pain you are experiencing right now, and I want you to be safe. "
    "Because I am an automated wellness system, I cannot provide crisis intervention or emergency medical care. "
    "Please connect with human emergency support immediately:\n\n"
    "• In the US/Canada: Call or text 988 (Suicide & Crisis Lifeline), available 24/7, free and confidential.\n"
    "• Crisis Text Line: Text HOME to 741741 to connect with a crisis counselor.\n"
    "• In the UK: Call 111 (NHS) or 999 in an emergency.\n"
    "• International: Contact your local emergency services or visit https://findahelpline.com to find free support in your country.\n\n"
    "You do not have to carry this alone—please reach out to one of these resources or a trusted professional right away."
)

SAFE_FALLBACK_RESPONSE = (
    "I want to support you, but as an automated wellness assistant, I cannot provide medical diagnoses, "
    "prescribe medications, or advise on altering medical treatments. "
    "Please consult a licensed doctor, psychiatrist, or healthcare professional for individualized medical guidance."
)

GENERATOR_ERROR_FALLBACK = (
    "I am here to support you, but I encountered a technical issue while generating a response. "
    "Please try again in a moment, or reach out to a trusted friend or support resource."
)


@runtime_checkable
class RetrievalProtocol(Protocol):
    """Protocol for injected knowledge retrieval services."""

    async def retrieve_relevant_chunks(
        self,
        query: str,
        top_k: int = 5,
        score_threshold: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """Asynchronously retrieves ranked KnowledgeChunk items matching query."""
        ...


@runtime_checkable
class ResponseGeneratorProtocol(Protocol):
    """Protocol for injected dialogue response generators."""

    async def generate_response(
        self,
        message: str,
        retrieved_chunks: Optional[List[Dict[str, Any]]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Asynchronously generates a dialogue response."""
        ...


class DeterministicFakeResponseGenerator:
    """Deterministic offline response generator for testing and local development.

    Privacy & Operational Guarantees:
    - Operates 100% locally with zero external network or OpenAI calls.
    - Deterministic and predictable response generation.
    - Records invocation calls for testing assertions.
    """

    def __init__(
        self,
        canned_response: Optional[str] = None,
        should_fail: bool = False,
        failure_exception: Optional[Exception] = None,
        canned_responses_map: Optional[Dict[str, str]] = None,
    ) -> None:
        self.canned_response = canned_response
        self.should_fail = should_fail
        self.failure_exception = failure_exception or RuntimeError("Simulated generator failure")
        self.canned_responses_map = canned_responses_map or {}
        self.calls: List[Dict[str, Any]] = []

    async def generate_response(
        self,
        message: str,
        retrieved_chunks: Optional[List[Dict[str, Any]]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        self.calls.append({
            "message_length": len(message),
            "chunks_count": len(retrieved_chunks) if retrieved_chunks else 0,
            "context": context,
        })
        if self.should_fail:
            raise self.failure_exception

        if message in self.canned_responses_map:
            return self.canned_responses_map[message]

        if self.canned_response is not None:
            return self.canned_response

        # Context-aware deterministic generation from retrieved educational material
        if retrieved_chunks:
            primary_item = retrieved_chunks[0]
            chunk_obj = primary_item.get("chunk")
            title = getattr(chunk_obj, "title", "educational materials") if chunk_obj else "educational materials"
            return (
                f"Thank you for sharing. Based on {title}, taking slow diaphragmatic breaths "
                "and practicing self-compassion can help soothe everyday stress."
            )

        return (
            "Thank you for sharing how you are feeling. I am here to listen and explore "
            "supportive, non-clinical coping strategies with you."
        )


class ConversationOrchestrator:
    """Orchestrates conversation turns by coordinating Safety Engine, Knowledge Retrieval,
    Response Generation, and Output Safety Validation.

    Privacy & Safety Guarantees:
    1. Pre-Generation Safety Check: Runs deterministic Safety Engine before any retrieval or generation.
    2. Crisis Interception: Diverts HIGH_RISK / IMMEDIATE_HUMAN_EMERGENCY_SUPPORT immediately,
       bypassing knowledge retrieval and ordinary response generation.
    3. Safe Retrieval Handling: Injects knowledge only through injected retrieval service.
       Never invents sources or pretends retrieval succeeded on error.
    4. Post-Generation Safety Validation: Inspects generated responses before returning to user.
       Blocks medical diagnoses, medication prescription advice, and self-harm content.
    5. Non-Diagnostic & Non-Prescriptive: Enforces non-clinical boundaries.
    6. Memory Separation: Never writes conversation content into Qdrant or long-term knowledge base.
    7. Privacy Logging: Never logs raw user messages, generated texts, access tokens, or secrets.
    """

    def __init__(
        self,
        retrieval_service: Optional[RetrievalProtocol] = None,
        response_generator: Optional[ResponseGeneratorProtocol] = None,
        crisis_safety_response: str = DEFAULT_CRISIS_SAFETY_RESPONSE,
        safe_fallback_response: str = SAFE_FALLBACK_RESPONSE,
        generator_error_fallback: str = GENERATOR_ERROR_FALLBACK,
    ) -> None:
        self.retrieval_service = retrieval_service
        self.response_generator = (
            response_generator if response_generator is not None else DeterministicFakeResponseGenerator()
        )
        self.crisis_safety_response = crisis_safety_response
        self.safe_fallback_response = safe_fallback_response
        self.generator_error_fallback = generator_error_fallback

    async def handle_turn(self, request: OrchestrationRequest) -> OrchestrationResponse:
        """Executes a single orchestrated conversation turn."""
        clean_message = request.message.strip()
        logger.info(
            f"Conversation turn started: conversation_id={request.conversation_id}, "
            f"user_id={request.user_id}, message_len={len(clean_message)}"
        )

        # Step 1: Run deterministic Safety Engine on incoming user message
        safety_result: SafetyResult = evaluate_message(clean_message)

        # Step 2: Intercept HIGH_RISK or IMMEDIATE_HUMAN_EMERGENCY_SUPPORT
        if (
            safety_result.state == SafetyState.HIGH_RISK
            or safety_result.recommended_action == RecommendedAction.IMMEDIATE_HUMAN_EMERGENCY_SUPPORT
        ):
            logger.warning(
                f"Safety interception triggered: state={safety_result.state}, "
                f"action={safety_result.recommended_action}, reasons={safety_result.reasons}"
            )
            # Immediate diversion: bypass retrieval and ordinary response generation
            return OrchestrationResponse(
                response_text=self.crisis_safety_response,
                safety_result=safety_result,
                sources=[],
                is_safety_diverted=True,
                fallback_triggered=False,
                fallback_reason=None,
            )

        # Step 3: Retrieve relevant knowledge for non-high-risk messages
        retrieved_chunks: List[Dict[str, Any]] = []
        sources: List[SourceProvenance] = []

        if self.retrieval_service is not None:
            try:
                retrieved_chunks = await self.retrieval_service.retrieve_relevant_chunks(
                    query=clean_message,
                    top_k=request.top_k,
                    score_threshold=request.score_threshold,
                )
                sources = self._extract_provenance(retrieved_chunks)
                logger.info(
                    f"Knowledge retrieval completed: chunks_found={len(retrieved_chunks)}, "
                    f"sources_count={len(sources)}"
                )
            except Exception as exc:
                # Handle retrieval failure safely: do not invent sources or pretend it succeeded
                logger.warning(f"Knowledge retrieval failed safely: error_type={type(exc).__name__}")
                retrieved_chunks = []
                sources = []

        # Step 4: Generate dialogue response via injected generator
        try:
            raw_generated_text = await self.response_generator.generate_response(
                message=clean_message,
                retrieved_chunks=retrieved_chunks,
                context={
                    "safety_state": safety_result.state.value,
                    "recommended_action": safety_result.recommended_action.value,
                },
            )
            logger.info(f"Response generated successfully: length={len(raw_generated_text)}")
        except Exception as exc:
            logger.error(f"Response generator error: error_type={type(exc).__name__}")
            return OrchestrationResponse(
                response_text=self.generator_error_fallback,
                safety_result=safety_result,
                sources=[],
                is_safety_diverted=False,
                fallback_triggered=True,
                fallback_reason="GENERATOR_ERROR",
            )

        # Step 5: Final response safety validation before presenting to user
        validation = validate_response_safety(raw_generated_text)
        if not validation.is_safe:
            logger.warning(
                f"Generated response failed safety validation: reasons={validation.reasons}, "
                f"violation={validation.violation_type}"
            )
            return OrchestrationResponse(
                response_text=self.safe_fallback_response,
                safety_result=safety_result,
                sources=[],
                is_safety_diverted=False,
                fallback_triggered=True,
                fallback_reason="UNSAFE_OUTPUT_BLOCKED",
            )

        # Step 6: Return validated response with preserved provenance
        return OrchestrationResponse(
            response_text=raw_generated_text,
            safety_result=safety_result,
            sources=sources,
            is_safety_diverted=False,
            fallback_triggered=False,
            fallback_reason=None,
        )

    def _extract_provenance(self, chunks: List[Dict[str, Any]]) -> List[SourceProvenance]:
        """Extracts source provenance strictly from actually returned knowledge chunks."""
        provenance_list: List[SourceProvenance] = []
        for item in chunks:
            if not isinstance(item, dict):
                continue
            chunk_obj = item.get("chunk")
            score = item.get("score")
            if isinstance(chunk_obj, KnowledgeChunk):
                provenance_list.append(
                    SourceProvenance(
                        document_id=chunk_obj.document_id,
                        chunk_id=chunk_obj.chunk_id,
                        title=chunk_obj.title,
                        source_name=chunk_obj.source_name,
                        source_url=str(chunk_obj.source_url) if chunk_obj.source_url else None,
                        topic=chunk_obj.topic,
                        score=score,
                    )
                )
            elif isinstance(chunk_obj, dict):
                provenance_list.append(
                    SourceProvenance(
                        document_id=chunk_obj.get("document_id", "unknown"),
                        chunk_id=chunk_obj.get("chunk_id"),
                        title=chunk_obj.get("title", "Educational Document"),
                        source_name=chunk_obj.get("source_name", "Curated Knowledge Base"),
                        source_url=str(chunk_obj.get("source_url")) if chunk_obj.get("source_url") else None,
                        topic=chunk_obj.get("topic"),
                        score=score,
                    )
                )
        return provenance_list
