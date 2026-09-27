import uuid
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.user import User


class ConversationService:
    """Service handling business logic for conversations and messages."""

    @staticmethod
    async def create_conversation(
        db: AsyncSession,
        user_id: Optional[uuid.UUID] = None
    ) -> Conversation:
        """Creates a new conversation session for a user.
        
        Temporary User Strategy for Sprint 1 (No Authentication):
        If user_id is provided and exists, use it.
        If user_id is omitted or does not exist, create a new User record.
        """
        target_user: Optional[User] = None

        if user_id is not None:
            stmt = select(User).where(User.id == user_id)
            result = await db.execute(stmt)
            target_user = result.scalar_one_or_none()

        if target_user is None:
            # Create a temporary user record for Sprint 1 development/testing
            target_user = User()
            db.add(target_user)
            await db.flush()

        conversation = Conversation(user_id=target_user.id)
        db.add(conversation)
        await db.commit()
        await db.refresh(conversation, attribute_names=["messages"])
        return conversation

    @staticmethod
    async def get_conversation_by_id(
        db: AsyncSession,
        conversation_id: uuid.UUID
    ) -> Optional[Conversation]:
        """Retrieves a conversation by ID with its messages.
        
        Note: User ownership isolation is omitted in Sprint 1 pending Authentication (Phase 4).
        """
        stmt = (
            select(Conversation)
            .where(Conversation.id == conversation_id)
            .options(selectinload(Conversation.messages))
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def add_message_to_conversation(
        db: AsyncSession,
        conversation_id: uuid.UUID,
        role: str,
        content: str
    ) -> Optional[Message]:
        """Adds a new message (user or assistant) to a conversation.
        
        Returns None if the parent conversation does not exist.
        """
        # Verify conversation exists
        conversation_stmt = select(Conversation).where(Conversation.id == conversation_id)
        conv_result = await db.execute(conversation_stmt)
        conversation = conv_result.scalar_one_or_none()

        if conversation is None:
            return None

        message = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
        )
        db.add(message)
        await db.commit()
        await db.refresh(message)
        return message
