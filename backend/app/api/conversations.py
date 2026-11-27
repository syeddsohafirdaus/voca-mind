
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_role
from app.database import get_db
from app.logger import logger
from app.models.user import User
from app.safety.support_offer import build_support_offer
from app.services.support_availability import (
    has_open_professional_support,
)
from app.schemas.conversation import (
    ConversationCreate,
    ConversationResponse,
)
from app.schemas.message import MessageCreate, MessageResponse
from app.schemas.orchestrator import (
    ConversationHistoryMessage,
    OrchestrationRequest,
)
from app.services.conversation_orchestrator import ConversationOrchestrator
from app.services.conversation_service import ConversationService
from app.services.orchestrator_factory import get_orchestrator


router = APIRouter()

# All endpoints in this router require an active client account.
# Doctors and guardians cannot use these endpoints to access
# clients' private AI conversations.
get_current_client = require_role(["client"])


@router.get(
    "",
    response_model=list[ConversationResponse],
    status_code=status.HTTP_200_OK,
    summary="List Conversations",
)
async def list_conversations(
    current_user: User = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
) -> list[ConversationResponse]:
    """Return the authenticated client's previous conversations."""

    conversations = await ConversationService.list_conversations(
        db=db,
        user_id=current_user.id,
    )

    return [
        ConversationResponse.model_validate(conversation)
        for conversation in conversations
    ]


@router.post(
    "",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Conversation",
    description=(
        "Starts a new conversation for the authenticated client. "
        "Identity is extracted from the verified Firebase token."
    ),
)
async def create_conversation(
    payload: ConversationCreate = ConversationCreate(),
    current_user: User = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
) -> ConversationResponse:
    """Create a conversation owned by the authenticated client."""

    conversation = await ConversationService.create_conversation(
        db=db,
        user=current_user,
    )

    return ConversationResponse.model_validate(conversation)


@router.get(
    "/{conversation_id}",
    response_model=ConversationResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Conversation",
    description=(
        "Retrieves a conversation and its messages. "
        "Only the client who owns it may access it."
    ),
)
async def get_conversation(
    conversation_id: uuid.UUID,
    current_user: User = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
) -> ConversationResponse:
    """Retrieve a conversation with ownership enforcement."""

    conversation = await ConversationService.get_conversation_by_id(
        db=db,
        conversation_id=conversation_id,
        user_id=current_user.id,
    )

    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )

    return ConversationResponse.model_validate(conversation)


@router.post(
    "/{conversation_id}/messages",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Send Message to Conversation",
    description=(
        "Submits a client message to an owned conversation. "
        "Runs the safety evaluation, knowledge retrieval, "
        "AI generation, and output validation pipeline "
        "before persisting the conversation turn."
    ),
)
async def add_message(
    conversation_id: uuid.UUID,
    payload: MessageCreate,
    current_user: User = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
    orchestrator: ConversationOrchestrator = Depends(get_orchestrator),
) -> MessageResponse:
    """Process and save a client message and AI response."""

    # 1. Enforce conversation ownership.
    conversation = await ConversationService.get_conversation_by_id(
        db=db,
        conversation_id=conversation_id,
        user_id=current_user.id,
    )

    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )

    # 2. Only user messages may be submitted by the client.
    if payload.role != "user":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Clients can only submit 'user' messages. "
                "Assistant replies are generated server-side."
            ),
        )

    # 3. Load recent conversation history.
    previous_messages = sorted(
        (
            msg
            for msg in conversation.messages
            if msg.role in ("user", "assistant") and msg.content.strip()
        ),
        key=lambda msg: (msg.created_at, str(msg.id)),
    )

    recent_history = [
        ConversationHistoryMessage(
            role=msg.role,
            content=msg.content[:4000],
        )
        for msg in previous_messages[-10:]
    ]

    # 4. Run the existing AI orchestration pipeline.
    orchestration_req = OrchestrationRequest(
        message=payload.content,
        conversation_id=conversation_id,
        user_id=current_user.id,
        conversation_history=recent_history,
    )

    orchestration_resp = await orchestrator.handle_turn(
        orchestration_req
    )

    # 5. Persist the client message and AI response atomically.
    try:
        persisted = await ConversationService.persist_turn(
            db=db,
            conversation_id=conversation_id,
            user_id=current_user.id,
            user_content=payload.content,
            assistant_content=orchestration_resp.response_text,
        )
    except Exception:
        logger.error(
            "Message persistence failed: error_type=DatabaseError"
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred. Please try again.",
        )

    if persisted is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )

    user_msg, assistant_msg = persisted

    # 6. Return the persisted message and AI reply.
    assistant_msg_resp = MessageResponse.model_validate(
        assistant_msg
    )

    response = MessageResponse(
        id=user_msg.id,
        conversation_id=user_msg.conversation_id,
        role=user_msg.role,
        content=user_msg.content,
        created_at=user_msg.created_at,
        assistant_reply=assistant_msg_resp,
        sources=orchestration_resp.sources,
        is_safety_diverted=orchestration_resp.is_safety_diverted,
        support_offer=None,
    )

    support_offer = build_support_offer(
        orchestration_resp.safety_result
    )

    if support_offer.offered:
        try:
            has_open_support = await has_open_professional_support(
                db, current_user.id
            )
            support_offer = build_support_offer(
                orchestration_resp.safety_result,
                has_open_support=has_open_support,
            )
        except Exception:
            await db.rollback()
            logger.warning(
                "Support availability check failed"
            )

    response.support_offer = support_offer
    return response
