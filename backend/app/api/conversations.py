import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.user import User
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
        "Starts a new conversation session for the authenticated user. "
        "User identity is extracted from the verified Firebase Authorization Bearer token."
    )
)
async def create_conversation(
    payload: ConversationCreate = ConversationCreate(),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConversationResponse:
    """Creates a conversation bound to the authenticated current user."""
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
        "Retrieves a conversation by ID along with its associated messages. "
        "Enforces ownership: users can only access their own conversations."
    )
)
async def get_conversation(
    conversation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConversationResponse:
    """Retrieves conversation enforcing user ownership."""
    conversation = await ConversationService.get_conversation_by_id(
        db=db,
        conversation_id=conversation_id,
        user_id=current_user.id,
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
        "Enforces ownership: users can only add messages to their own conversations."
    )
)
async def add_message(
    conversation_id: uuid.UUID,
    payload: MessageCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Adds a message enforcing user ownership of the parent conversation."""
    message = await ConversationService.add_message_to_conversation(
        db=db,
        conversation_id=conversation_id,
        user_id=current_user.id,
        role=payload.role,
        content=payload.content,
    )
    if message is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )
    return MessageResponse.model_validate(message)
