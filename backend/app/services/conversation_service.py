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

    @staticmethod
    async def persist_turn(
        db: AsyncSession,
        conversation_id: uuid.UUID,
        user_id: uuid.UUID,
        user_content: str,
        assistant_content: str,
    ) -> Optional[tuple[Message, Message]]:
        """Atomically persists a user message and its generated assistant reply.

        Enforces conversation ownership: returns None if the parent conversation
        does not exist or belongs to another user.
        Both messages are committed in a single atomic transaction.
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

        user_message = Message(
            conversation_id=conversation_id,
            role="user",
            content=user_content,
        )
        assistant_message = Message(
            conversation_id=conversation_id,
            role="assistant",
            content=assistant_content,
        )
        db.add(user_message)
        db.add(assistant_message)

        await db.commit()
        await db.refresh(user_message)
        await db.refresh(assistant_message)

        return user_message, assistant_message
