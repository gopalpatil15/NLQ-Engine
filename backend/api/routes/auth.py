from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from pydantic import BaseModel
from backend.services.history_service import HistoryService
from backend.services.auth_service import create_access_token, authenticate_user

router = APIRouter()
security = HTTPBearer()

# Lazy initialization of history service
_history_service = None

def get_history_service():
    global _history_service
    if _history_service is None:
        _history_service = HistoryService()
    return _history_service

class UserCreate(BaseModel):
    username: str
    password: str

class UserLogin(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str

def get_db():
    """Get database session"""
    history_service = get_history_service()
    db = history_service.get_db()
    try:
        yield db
    finally:
        db.close()

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
    """Dependency to get current authenticated user"""
    from backend.services.auth_service import get_current_user as _get_current_user
    return _get_current_user(credentials.credentials, db)

@router.post("/register", response_model=TokenResponse)
async def register(user: UserCreate, db: Session = Depends(get_db)):
    """Register a new user"""
    try:
        # Create user
        history_service = get_history_service()
        new_user = history_service.create_user(user.username, user.password)

        # Create access token
        access_token = create_access_token(data={"sub": new_user.username})

        return TokenResponse(access_token=access_token, username=new_user.username)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed"
        )

@router.post("/login", response_model=TokenResponse)
async def login(user: UserLogin, db: Session = Depends(get_db)):
    """Login user"""
    try:
        # Authenticate user
        db_user = authenticate_user(db, user.username, user.password)
        if not db_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Create access token
        access_token = create_access_token(data={"sub": db_user.username})

        return TokenResponse(access_token=access_token, username=db_user.username)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed"
        )