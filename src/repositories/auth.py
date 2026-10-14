from datetime import datetime

from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, select

from src.models.models import RefreshSession, RefreshToken


class AuthRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_session(self, session: RefreshSession, token: RefreshToken) -> None:
        try:
            self.db.add(session)
            self.db.flush()
            self.db.add(token)
            self.db.commit()
        except SQLAlchemyError:
            self.db.rollback()
            raise

    def find_for_update(
        self, token_hash: str
    ) -> tuple[RefreshSession, RefreshToken] | None:
        """Serialize all rotations/replays of a family on its session row."""
        try:
            session_id = self.db.exec(
                select(RefreshToken.session_id).where(RefreshToken.token_hash == token_hash)
            ).one_or_none()
            if session_id is None:
                return None

            session = self.db.exec(
                select(RefreshSession)
                .where(RefreshSession.id == session_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            ).one_or_none()
            if session is None:
                return None

            # A locking read sees the latest committed value even under MySQL's
            # REPEATABLE READ. Always acquire the session lock before this one.
            token = self.db.exec(
                select(RefreshToken)
                .where(RefreshToken.token_hash == token_hash)
                .with_for_update()
                .execution_options(populate_existing=True)
            ).one_or_none()
            return (session, token) if token is not None else None
        except SQLAlchemyError:
            self.db.rollback()
            raise

    def rotate(
        self, previous: RefreshToken, replacement: RefreshToken, now: datetime
    ) -> None:
        try:
            previous.used_at = now
            self.db.add(previous)
            self.db.add(replacement)
            self.db.commit()
        except SQLAlchemyError:
            self.db.rollback()
            raise

    def revoke(self, session: RefreshSession, now: datetime) -> None:
        try:
            session.revoked_at = now
            self.db.add(session)
            self.db.commit()
        except SQLAlchemyError:
            self.db.rollback()
            raise
