import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.auth.dependencies import get_current_user
from app.database import get_db
from app.logger import logger
from app.models.user import User
from app.schemas.conversation import ConversationCreate, ConversationResponse
from app.schemas.message import MessageCreate, MessageResponse
from app.schemas.orchestrator import OrchestrationRequest
from app.services.conversation_orchestrator import ConversationOrchestrator
from app.services.conversation_service import ConversationService
from app.services.orchestrator_factory import get_orchestrator

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
    summary="Send Message to Conversation",
    description=(
        "Submits a user message to an active conversation session. "
        "Executes the full safety evaluation, knowledge retrieval, AI generation, and "
        "output validation orchestration pipeline before atomically persisting user and assistant messages. "
        "Enforces ownership: users can only send messages to their own conversations."
    )
)
async def add_message(
    conversation_id: uuid.UUID,
    payload: MessageCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    orchestrator: ConversationOrchestrator = Depends(get_orchestrator),
) -> MessageResponse:
    """Sends a user message, runs the orchestration pipeline, and atomically persists the turn."""
    # 1. Enforce conversation existence and user ownership
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

    # 2. Enforce: clients may only submit user messages; assistant replies are server-generated
    if payload.role != "user":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Clients can only submit 'user' messages. Assistant replies are generated server-side.",
        )

    # 3. Execute orchestration turn (safety pre-check, retrieval, AI generation, output validation)
    orchestration_req = OrchestrationRequest(
        message=payload.content,
        conversation_id=conversation_id,
        user_id=current_user.id,
    )
    orchestration_resp = await orchestrator.handle_turn(orchestration_req)

    # 4. Atomically persist both user message and assistant reply in a single transaction
    try:
        persisted = await ConversationService.persist_turn(
            db=db,
            conversation_id=conversation_id,
            user_id=current_user.id,
            user_content=payload.content,
            assistant_content=orchestration_resp.response_text,
        )
    except Exception:
        # db.rollback() is guaranteed by the get_db() session context manager.
        # Log only the error category — never the user message, assistant content, or SQL detail.
        logger.error("Message persistence failed: error_type=DatabaseError")
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

    # 5. Build enriched response payload containing user message and server-generated assistant reply
    assistant_msg_resp = MessageResponse.model_validate(assistant_msg)
    return MessageResponse(
        id=user_msg.id,
        conversation_id=user_msg.conversation_id,
        role=user_msg.role,
        content=user_msg.content,
        created_at=user_msg.created_at,
        assistant_reply=assistant_msg_resp,
        sources=orchestration_resp.sources,
        is_safety_diverted=orchestration_resp.is_safety_diverted,
    )
