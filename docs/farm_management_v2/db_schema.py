"""
農業管理アプリ v2.0 - データベーススキーマ定義

SQLAlchemy ORM モデル + Pydantic スキーマ
"""

from datetime import datetime, date
from typing import Optional, List
import os

from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Float,
    Boolean,
    Text,
    DateTime,
    Date,
    ForeignKey,
)
from sqlalchemy.orm import (
    declarative_base,
    relationship,
    sessionmaker,
    Session,
)
from pydantic import BaseModel, ConfigDict

# =============================================================================
# データベース設定
# =============================================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_PATH = os.path.join(BASE_DIR, "farm_management.db")
DATABASE_URL = f"sqlite:///{DATABASE_PATH}"

engine = create_engine(DATABASE_URL, echo=False, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


# =============================================================================
# SQLAlchemy ORM モデル
# =============================================================================

class Farmer(Base):
    """農家/ユーザーテーブル"""
    __tablename__ = "farmers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # リレーションシップ
    fields = relationship("Field", back_populates="farmer", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Farmer(id={self.id}, name='{self.name}', email='{self.email}')>"


class Field(Base):
    """ほ場情報テーブル"""
    __tablename__ = "fields"

    id = Column(Integer, primary_key=True, index=True)
    farmer_id = Column(Integer, ForeignKey("farmers.id", ondelete="CASCADE"), nullable=False, index=True)
    field_name = Column(String(100), nullable=False)
    district = Column(String(100), nullable=True)
    area_ha = Column(Float, nullable=False)
    polygon_geojson = Column(Text, nullable=True)  # GeoJSON形式のポリゴンデータ
    beet_forbidden = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # リレーションシップ
    farmer = relationship("Farmer", back_populates="fields")
    crop_plans = relationship("CropPlan", back_populates="field", cascade="all, delete-orphan")
    pesticide_usages = relationship("PesticideUsage", back_populates="field", cascade="all, delete-orphan")
    yields = relationship("Yield", back_populates="field", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Field(id={self.id}, name='{self.field_name}', area={self.area_ha}ha)>"


class CropPlan(Base):
    """作付計画テーブル"""
    __tablename__ = "crop_plans"

    id = Column(Integer, primary_key=True, index=True)
    field_id = Column(Integer, ForeignKey("fields.id", ondelete="CASCADE"), nullable=False, index=True)
    year = Column(Integer, nullable=False, index=True)
    crop = Column(String(50), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # リレーションシップ
    field = relationship("Field", back_populates="crop_plans")

    def __repr__(self):
        return f"<CropPlan(id={self.id}, year={self.year}, crop='{self.crop}')>"


class PesticideUsage(Base):
    """農薬使用履歴テーブル"""
    __tablename__ = "pesticide_usage"

    id = Column(Integer, primary_key=True, index=True)
    field_id = Column(Integer, ForeignKey("fields.id", ondelete="CASCADE"), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    pesticide_name = Column(String(100), nullable=False)
    amount = Column(Float, nullable=False)
    unit = Column(String(20), nullable=False)
    target = Column(String(100), nullable=True)  # 対象病害虫
    weather = Column(String(50), nullable=True)  # 天候（任意）
    notes = Column(Text, nullable=True)  # 備考
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # リレーションシップ
    field = relationship("Field", back_populates="pesticide_usages")

    def __repr__(self):
        return f"<PesticideUsage(id={self.id}, date={self.date}, pesticide='{self.pesticide_name}')>"


class Yield(Base):
    """収量記録テーブル"""
    __tablename__ = "yields"

    id = Column(Integer, primary_key=True, index=True)
    field_id = Column(Integer, ForeignKey("fields.id", ondelete="CASCADE"), nullable=False, index=True)
    year = Column(Integer, nullable=False, index=True)
    crop = Column(String(50), nullable=False)
    yield_kg = Column(Float, nullable=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # リレーションシップ
    field = relationship("Field", back_populates="yields")

    def __repr__(self):
        return f"<Yield(id={self.id}, year={self.year}, crop='{self.crop}', yield={self.yield_kg}kg)>"


# =============================================================================
# Pydantic スキーマ（CRUD用）
# =============================================================================

# -----------------------------------------------------------------------------
# Farmer スキーマ
# -----------------------------------------------------------------------------

class FarmerBase(BaseModel):
    name: str
    email: str


class FarmerCreate(FarmerBase):
    password: str


class FarmerUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = None


class FarmerResponse(FarmerBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FarmerWithFields(FarmerResponse):
    fields: List["FieldResponse"] = []


# -----------------------------------------------------------------------------
# Field スキーマ
# -----------------------------------------------------------------------------

class FieldBase(BaseModel):
    field_name: str
    district: Optional[str] = None
    area_ha: float
    polygon_geojson: Optional[str] = None
    beet_forbidden: bool = False


class FieldCreate(FieldBase):
    farmer_id: int


class FieldUpdate(BaseModel):
    field_name: Optional[str] = None
    district: Optional[str] = None
    area_ha: Optional[float] = None
    polygon_geojson: Optional[str] = None
    beet_forbidden: Optional[bool] = None


class FieldResponse(FieldBase):
    id: int
    farmer_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FieldWithPlans(FieldResponse):
    crop_plans: List["CropPlanResponse"] = []
    yields: List["YieldResponse"] = []


# -----------------------------------------------------------------------------
# CropPlan スキーマ
# -----------------------------------------------------------------------------

class CropPlanBase(BaseModel):
    year: int
    crop: str


class CropPlanCreate(CropPlanBase):
    field_id: int


class CropPlanUpdate(BaseModel):
    year: Optional[int] = None
    crop: Optional[str] = None


class CropPlanResponse(CropPlanBase):
    id: int
    field_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# -----------------------------------------------------------------------------
# PesticideUsage スキーマ
# -----------------------------------------------------------------------------

class PesticideUsageBase(BaseModel):
    date: date
    pesticide_name: str
    amount: float
    unit: str
    target: Optional[str] = None
    weather: Optional[str] = None
    notes: Optional[str] = None


class PesticideUsageCreate(PesticideUsageBase):
    field_id: int


class PesticideUsageUpdate(BaseModel):
    date: Optional[date] = None
    pesticide_name: Optional[str] = None
    amount: Optional[float] = None
    unit: Optional[str] = None
    target: Optional[str] = None
    weather: Optional[str] = None
    notes: Optional[str] = None


class PesticideUsageResponse(PesticideUsageBase):
    id: int
    field_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# -----------------------------------------------------------------------------
# Yield スキーマ
# -----------------------------------------------------------------------------

class YieldBase(BaseModel):
    year: int
    crop: str
    yield_kg: float
    notes: Optional[str] = None


class YieldCreate(YieldBase):
    field_id: int


class YieldUpdate(BaseModel):
    year: Optional[int] = None
    crop: Optional[str] = None
    yield_kg: Optional[float] = None
    notes: Optional[str] = None


class YieldResponse(YieldBase):
    id: int
    field_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# データベース操作関数
# =============================================================================

def init_db():
    """データベースを初期化（テーブル作成）"""
    Base.metadata.create_all(bind=engine)


def drop_db():
    """全テーブルを削除（開発用）"""
    Base.metadata.drop_all(bind=engine)


def get_db() -> Session:
    """データベースセッションを取得（依存性注入用）"""
    db = SessionLocal()
    try:
        return db
    except Exception:
        db.close()
        raise


def get_db_context():
    """コンテキストマネージャー形式でセッションを取得"""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# =============================================================================
# ユーティリティ関数
# =============================================================================

def hash_password(password: str) -> str:
    """パスワードをハッシュ化（簡易版、本番ではbcrypt等を使用）"""
    import hashlib
    return hashlib.sha256(password.encode()).hexdigest()


def verify_password(password: str, password_hash: str) -> bool:
    """パスワードを検証"""
    return hash_password(password) == password_hash


# =============================================================================
# 初期化
# =============================================================================

if __name__ == "__main__":
    print("データベースを初期化しています...")
    init_db()
    print(f"データベースを作成しました: {DATABASE_PATH}")

    # テスト用データ作成
    db = SessionLocal()
    try:
        # サンプル農家を作成
        farmer = Farmer(
            name="テスト農家",
            email="test@example.com",
            password_hash=hash_password("password123")
        )
        db.add(farmer)
        db.commit()
        db.refresh(farmer)
        print(f"サンプル農家を作成しました: {farmer}")

        # サンプルほ場を作成
        field = Field(
            farmer_id=farmer.id,
            field_name="北1号",
            district="北地区",
            area_ha=2.8,
            beet_forbidden=False
        )
        db.add(field)
        db.commit()
        db.refresh(field)
        print(f"サンプルほ場を作成しました: {field}")

        # サンプル作付計画を作成
        plan = CropPlan(
            field_id=field.id,
            year=2026,
            crop="春小麦"
        )
        db.add(plan)
        db.commit()
        print(f"サンプル作付計画を作成しました: {plan}")

        print("\n初期化完了！")
    finally:
        db.close()
