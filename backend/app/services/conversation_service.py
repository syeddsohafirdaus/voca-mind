import uuid
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.user import User


class ConversationService:
    """Service handling business logic for conversations and messages with user ownership enforcement."""

    @staticmethod
    async def create_conversation(
        db: AsyncSession,
        user: User,
    ) -> Conversation:
        """Creates a new conversation session for an authenticated user."""
        conversation = Conversation(user_id=user.id)
        db.add(conversation)
        await db.commit()
        await db.refresh(conversation, attribute_names=["messages"])
        return conversation

    @staticmethod
    async def get_conversation_by_id(
        db: AsyncSession,
        conversation_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Optional[Conversation]:
        """Retrieves a conversation by ID for a specific authenticated user.
        
        Enforces user ownership: returns None if the conversation does not exist
        or belongs to another user.
        """
        stmt = (
            select(Conversation)
            .where(
                Conversation.id == conversation_id,
                Conversation.user_id == user_id,
            )
            .options(selectinload(Conversation.messages))
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def add_message_to_conversation(
        db: AsyncSession,
        conversation_id: uuid.UUID,
        user_id: uuid.UUID,
        role: str,
        content: str,
    ) -> Optional[Message]:
        """Adds a new message (user or assistant) to an authenticated user's conversation.
        
        Enforces user ownership: returns None if the parent conversation does not exist
        or belongs to another user.
        """
        # Verify conversation exists and belongs to the authenticated user
        conversation_stmt = select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id,
        )
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
