from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, Boolean, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
from datetime import datetime
import os

Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationship to query history
    query_history = relationship("QueryHistory", back_populates="user")

class QueryHistory(Base):
    __tablename__ = "query_history"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    query_text = Column(Text)
    mode = Column(String)  # 'llm' or 'sql'
    generated_sql = Column(Text, nullable=True)
    connection_string = Column(String)
    status = Column(String)  # 'success' or 'error'
    error_message = Column(Text, nullable=True)
    response_time = Column(Integer, nullable=True)  # in milliseconds
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationship to user
    user = relationship("User", back_populates="query_history")

class HistoryService:
    def __init__(self, database_url: str = None):
        if database_url is None:
            # Use a local SQLite database for app metadata
            db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "app_metadata.db")
            database_url = f"sqlite:///{db_path}"

        self.engine = create_engine(database_url, connect_args={"check_same_thread": False})
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

        # Don't create tables here - do it lazily when first accessed
        self._tables_created = False

    def _ensure_tables_created(self):
        if not self._tables_created:
            Base.metadata.create_all(bind=self.engine)
            self._tables_created = True

    def get_db(self) -> Session:
        """Get database session"""
        self._ensure_tables_created()
        return self.SessionLocal()

    def create_user(self, username: str, password: str) -> User:
        """Create a new user"""
        from backend.services.auth_service import get_password_hash

        db = self.get_db()
        try:
            # Check if user already exists
            existing_user = db.query(User).filter(User.username == username).first()
            if existing_user:
                raise ValueError("Username already exists")

            hashed_password = get_password_hash(password)
            user = User(username=username, hashed_password=hashed_password)
            db.add(user)
            db.commit()
            db.refresh(user)
            return user
        finally:
            db.close()

    def authenticate_user(self, username: str, password: str) -> User:
        """Authenticate user"""
        from backend.services.auth_service import authenticate_user
        db = self.get_db()
        try:
            return authenticate_user(db, username, password)
        finally:
            db.close()

    def store_history(self, user_id: int, query_text: str, mode: str, connection_string: str,
                     generated_sql: str = None, status: str = "success",
                     error_message: str = None, response_time: int = None):
        """Store query history"""
        db = self.get_db()
        try:
            history = QueryHistory(
                user_id=user_id,
                query_text=query_text,
                mode=mode,
                generated_sql=generated_sql,
                connection_string=connection_string,
                status=status,
                error_message=error_message,
                response_time=response_time
            )
            db.add(history)
            db.commit()
            db.refresh(history)
            return history
        finally:
            db.close()

    def get_user_history(self, user_id: int, limit: int = 50) -> list:
        """Get user's query history"""
        db = self.get_db()
        try:
            history = db.query(QueryHistory).filter(
                QueryHistory.user_id == user_id
            ).order_by(QueryHistory.created_at.desc()).limit(limit).all()

            return [
                {
                    "id": h.id,
                    "query_text": h.query_text,
                    "mode": h.mode,
                    "generated_sql": h.generated_sql,
                    "connection_string": h.connection_string,
                    "status": h.status,
                    "error_message": h.error_message,
                    "response_time": h.response_time,
                    "created_at": h.created_at.isoformat()
                }
                for h in history
            ]
        finally:
            db.close()