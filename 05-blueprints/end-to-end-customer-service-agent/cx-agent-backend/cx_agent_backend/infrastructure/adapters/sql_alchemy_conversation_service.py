# infrastructure/sqlalchemy_conversation_repository.py
import uuid

from sqlalchemy.orm import Session

from cx_agent_backend.domain.repositories.conversation_repository import (
    ConversationRepository,
)
from cx_agent_backend.domain.entities.conversation import Conversation, Message
from cx_agent_backend.presentation.schemas.conversation_schemas import (
    ConversationSchema,
    MessageSchema,
    ConversationUserDB,
)  # your SQLAlchemy models


class SQLAlchemyConversationRepository(ConversationRepository):
    def __init__(self, session: Session):
        self.session = session

    def save(self, conversation: Conversation) -> None:
        convo_db = ConversationSchema(
            id=conversation.id, created_at=conversation.created_at
        )
        for uid in conversation.user_ids:
            convo_db.users.append(ConversationUserDB(user_id=uid))
        self.session.add(convo_db)
        self.session.commit()

    def get_by_id(self, conversation_id: uuid.UUID) -> Conversation:
        convo_db = (
            self.session.query(ConversationSchema).filter_by(id=conversation_id).first()
        )
        if not convo_db:
            return None
        return Conversation(
            id=convo_db.id,
            user_ids=[u.user_id for u in convo_db.users],
            messages=[
                Message(
                    id=m.id, sender_id=m.sender_id, text=m.text, created_at=m.created_at
                )
                for m in convo_db.messages
            ],
            created_at=convo_db.created_at,
        )

    def add_message(self, conversation_id: uuid.UUID, message: Message) -> None:
        msg_db = MessageSchema(
            id=message.id,
            conversation_id=conversation_id,
            sender_id=message.sender_id,
            text=message.text,
            created_at=message.created_at,
        )
        self.session.add(msg_db)
        self.session.commit()
