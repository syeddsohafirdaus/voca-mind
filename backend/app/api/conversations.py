import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.schemas.conversation import ConversationCreate, ConversationResponse
from app.schemas.message import MessageCreate, MessageResponse
from app.services.conversation_service import ConversationService

router = APIRouter()


@router.post(
    "",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Conversation",
    description=(
        "Starts a new conversation session for a user. "
        "Authentication is NOT implemented in Sprint 1. "
        "For testing, an optional user_id may be supplied; if omitted, a temporary user record is generated."
    )
)
async def create_conversation(
    payload: ConversationCreate = ConversationCreate(),
    db: AsyncSession = Depends(get_db),
) -> ConversationResponse:
    """Delegates conversation creation to ConversationService."""
    conversation = await ConversationService.create_conversation(
        db=db,
        user_id=payload.user_id,
    )
    return ConversationResponse.model_validate(conversation)


@router.get(
    "/{conversation_id}",
    response_model=ConversationResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Conversation",
    description=(
        "Retrieves a conversation by ID along with its associated messages. "
        "Note: Ownership checks are omitted in Sprint 1 pending authentication implementation (Phase 4)."
    )
)
async def get_conversation(
    conversation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> ConversationResponse:
    """Delegates conversation retrieval to ConversationService."""
    conversation = await ConversationService.get_conversation_by_id(
        db=db,
        conversation_id=conversation_id,
    )
    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )
    return ConversationResponse.model_validate(conversation)


@router.post(
    "/{conversation_id}/messages",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add Message to Conversation",
    description=(
        "Adds a new message (role: 'user' or 'assistant') to an existing conversation. "
        "This endpoint stores the message directly without triggering LLM inference or AI dialogue generation."
    )
)
async def add_message(
    conversation_id: uuid.UUID,
    payload: MessageCreate,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Delegates message creation to ConversationService."""
    message = await ConversationService.add_message_to_conversation(
        db=db,
        conversation_id=conversation_id,
        role=payload.role,
        content=payload.content,
    )
    if message is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )
    return MessageResponse.model_validate(message)
