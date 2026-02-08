"""
農業管理アプリ v2.0 - FastAPI基盤と認証機能
============================================
FastAPIアプリケーションの基盤とJWT認証を提供する。
"""

import os
import warnings
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

# db_schema.py からのインポート（足軽1が作成）
from db_schema import Base, User, engine, SessionLocal


# =============================================================================
# JWT設定
# =============================================================================
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

# 本番環境でデフォルトキー使用時の警告
if SECRET_KEY == "dev-secret-key-change-in-production":
    warnings.warn(
        "WARNING: Using default SECRET_KEY. Set SECRET_KEY environment variable in production!",
        UserWarning
    )


# =============================================================================
# パスワードハッシュ設定
# =============================================================================
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# =============================================================================
# OAuth2設定
# =============================================================================
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


# =============================================================================
# Pydanticスキーマ
# =============================================================================
class UserCreate(BaseModel):
    """ユーザー登録リクエスト"""
    username: str
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    """ユーザー情報レスポンス"""
    id: int
    username: str
    email: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class Token(BaseModel):
    """JWTトークンレスポンス"""
    access_token: str
    token_type: str


class TokenData(BaseModel):
    """トークンデータ（内部使用）"""
    username: Optional[str] = None


# =============================================================================
# FastAPIアプリケーション
# =============================================================================
app = FastAPI(
    title="農業管理アプリ API",
    description="農業管理アプリ v2.0 のバックエンドAPI",
    version="2.0.0"
)

# CORSミドルウェア設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 本番環境では適切に制限すること
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# 起動時イベント
# =============================================================================
@app.on_event("startup")
def on_startup():
    """アプリケーション起動時にDBを初期化"""
    Base.metadata.create_all(bind=engine)


# =============================================================================
# 依存性注入
# =============================================================================
def get_db():
    """データベースセッションを取得"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    """JWTトークンを検証し、現在のユーザーを取得"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="認証情報を検証できませんでした",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception

    user = db.query(User).filter(User.username == token_data.username).first()
    if user is None:
        raise credentials_exception
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="アカウントが無効化されています"
        )
    return user


# =============================================================================
# ヘルパー関数
# =============================================================================
def verify_password(plain_password: str, hashed_password: str) -> bool:
    """パスワードを検証"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """パスワードをハッシュ化"""
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """JWTアクセストークンを生成"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def authenticate_user(db: Session, username: str, password: str) -> Optional[User]:
    """ユーザー認証"""
    user = db.query(User).filter(User.username == username).first()
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


# =============================================================================
# 認証エンドポイント
# =============================================================================
@app.post("/auth/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(user: UserCreate, db: Session = Depends(get_db)):
    """
    ユーザー登録

    新規ユーザーを作成し、登録情報を返す。
    """
    # ユーザー名の重複チェック
    existing_user = db.query(User).filter(User.username == user.username).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="このユーザー名は既に使用されています"
        )

    # メールアドレスの重複チェック
    existing_email = db.query(User).filter(User.email == user.email).first()
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="このメールアドレスは既に使用されています"
        )

    # ユーザー作成
    hashed_password = get_password_hash(user.password)
    db_user = User(
        username=user.username,
        email=user.email,
        hashed_password=hashed_password
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    return db_user


@app.post("/auth/login", response_model=Token)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """
    ログイン

    ユーザー名とパスワードで認証し、JWTトークンを発行する。
    """
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="ユーザー名またはパスワードが正しくありません",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username},
        expires_delta=access_token_expires
    )

    return {"access_token": access_token, "token_type": "bearer"}


@app.get("/auth/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    """
    現在のユーザー情報取得

    認証済みユーザーの情報を返す。
    """
    return current_user


@app.post("/auth/logout", status_code=status.HTTP_200_OK)
def logout(current_user: User = Depends(get_current_user)):
    """
    ログアウト

    クライアント側でトークンを削除することでログアウトを実現。
    サーバー側では認証確認のみ行う。
    """
    return {"message": "ログアウトしました", "username": current_user.username}


# =============================================================================
# ヘルスチェック
# =============================================================================
@app.get("/health")
def health_check():
    """ヘルスチェック"""
    return {"status": "healthy", "version": "2.0.0"}


# =============================================================================
# 起動方法
# =============================================================================
# cd /home/yasu/multi-agent-shogun/docs/farm_management_v2
# uvicorn api_base:app --reload
