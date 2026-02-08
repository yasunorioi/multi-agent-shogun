"""
農業管理アプリ v2.0 - 収量記録API
==================================
収量記録のCRUD操作と統計・集計機能を提供する。

エンドポイント一覧:
  CRUD操作:
    POST   /api/yields              - 収量記録登録
    GET    /api/yields              - 収量一覧取得（フィルタ可能）
    GET    /api/yields/{yield_id}   - 収量詳細取得
    PUT    /api/yields/{yield_id}   - 収量更新
    DELETE /api/yields/{yield_id}   - 収量削除

  集計機能:
    GET    /api/yields/summary/by-year/{year}   - 年別収量サマリ
    GET    /api/yields/summary/by-crop/{crop}   - 作物別収量推移
    GET    /api/yields/stats/{field_id}         - ほ場別統計
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from db_schema import (
    Yield,
    YieldCreate,
    YieldUpdate,
    YieldResponse,
    Field,
)
from api_base import get_db, get_current_user


# =============================================================================
# Router設定
# =============================================================================
router = APIRouter(prefix="/api/yields", tags=["yields"])


# =============================================================================
# 追加Pydanticスキーマ（集計機能用）
# =============================================================================
class CropYieldSummaryItem(BaseModel):
    """作物別収量サマリアイテム"""
    crop: str
    total_yield_kg: float
    total_area_ha: float
    yield_per_ha: float  # 平均反収（kg/ha）
    field_count: int


class YearSummaryResponse(BaseModel):
    """年別収量サマリレスポンス"""
    year: int
    total_yield_kg: float
    total_area_ha: float
    crops: List[CropYieldSummaryItem]


class YearYieldItem(BaseModel):
    """年別収量アイテム（作物別推移用）"""
    year: int
    total_yield_kg: float
    total_area_ha: float
    yield_per_ha: float
    field_count: int


class CropYieldTrendResponse(BaseModel):
    """作物別収量推移レスポンス"""
    crop: str
    years: List[YearYieldItem]


class FieldYieldHistoryItem(BaseModel):
    """ほ場別収量履歴アイテム"""
    yield_id: int
    year: int
    crop: str
    yield_kg: float
    yield_per_ha: float
    notes: Optional[str]


class FieldStatsResponse(BaseModel):
    """ほ場別統計レスポンス"""
    field_id: int
    field_name: str
    area_ha: float
    total_records: int
    avg_yield_per_ha: float
    history: List[FieldYieldHistoryItem]


# =============================================================================
# ヘルパー関数
# =============================================================================
def verify_field_ownership(db: Session, field_id: int, user_id: int) -> Field:
    """
    ほ場の所有権を検証する。

    Args:
        db: データベースセッション
        field_id: ほ場ID
        user_id: ユーザーID（farmer_id）

    Returns:
        Field: 検証済みのほ場オブジェクト

    Raises:
        HTTPException: ほ場が存在しない、または所有権がない場合
    """
    field = db.query(Field).filter(Field.id == field_id).first()
    if not field:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"ほ場ID {field_id} が見つかりません"
        )
    if field.farmer_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="このほ場へのアクセス権限がありません"
        )
    return field


def verify_yield_ownership(db: Session, yield_id: int, user_id: int) -> Yield:
    """
    収量記録の所有権を検証する。

    Args:
        db: データベースセッション
        yield_id: 収量記録ID
        user_id: ユーザーID（farmer_id）

    Returns:
        Yield: 検証済みの収量記録オブジェクト

    Raises:
        HTTPException: 記録が存在しない、または所有権がない場合
    """
    yield_record = db.query(Yield).filter(Yield.id == yield_id).first()
    if not yield_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"収量記録ID {yield_id} が見つかりません"
        )

    field = db.query(Field).filter(Field.id == yield_record.field_id).first()
    if not field or field.farmer_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="この収量記録へのアクセス権限がありません"
        )
    return yield_record


def get_user_field_ids(db: Session, user_id: int) -> List[int]:
    """ユーザーのほ場IDリストを取得"""
    fields = db.query(Field).filter(Field.farmer_id == user_id).all()
    return [f.id for f in fields]


# =============================================================================
# CRUD操作エンドポイント
# =============================================================================
@router.post("", response_model=YieldResponse, status_code=status.HTTP_201_CREATED)
def create_yield(
    yield_data: YieldCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    """
    収量記録を登録する。

    認証必須。自分のほ場の記録のみ登録可能。
    """
    verify_field_ownership(db, yield_data.field_id, current_user.id)

    db_yield = Yield(
        field_id=yield_data.field_id,
        year=yield_data.year,
        crop=yield_data.crop,
        yield_kg=yield_data.yield_kg,
        notes=yield_data.notes
    )
    db.add(db_yield)
    db.commit()
    db.refresh(db_yield)

    return db_yield


@router.get("", response_model=List[YieldResponse])
def list_yields(
    field_id: Optional[int] = Query(None, description="ほ場IDでフィルタ"),
    year: Optional[int] = Query(None, description="年でフィルタ"),
    crop: Optional[str] = Query(None, description="作物名でフィルタ"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    """
    収量一覧を取得する。

    認証必須。自分のほ場の記録のみ取得可能。
    field_id, year, crop でフィルタ可能。
    """
    user_field_ids = get_user_field_ids(db, current_user.id)

    if not user_field_ids:
        return []

    query = db.query(Yield).filter(Yield.field_id.in_(user_field_ids))

    if field_id is not None:
        if field_id not in user_field_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="このほ場へのアクセス権限がありません"
            )
        query = query.filter(Yield.field_id == field_id)

    if year is not None:
        query = query.filter(Yield.year == year)

    if crop is not None:
        query = query.filter(Yield.crop == crop)

    yields = query.order_by(Yield.year.desc(), Yield.field_id).all()
    return yields


@router.get("/summary/by-year/{year}", response_model=YearSummaryResponse)
def get_yield_summary_by_year(
    year: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    """
    年別収量サマリを取得する。

    指定年の作物別の総収量、総面積、平均反収を返す。
    認証必須。自分のほ場の記録のみ集計。
    """
    user_field_ids = get_user_field_ids(db, current_user.id)

    if not user_field_ids:
        return YearSummaryResponse(
            year=year,
            total_yield_kg=0.0,
            total_area_ha=0.0,
            crops=[]
        )

    # ほ場情報を取得（面積用）
    fields_map = {
        f.id: f for f in db.query(Field).filter(Field.id.in_(user_field_ids)).all()
    }

    # 指定年の収量を取得
    yields = db.query(Yield).filter(
        Yield.field_id.in_(user_field_ids),
        Yield.year == year
    ).all()

    # 作物別に集計
    crop_data = {}
    for y in yields:
        field = fields_map.get(y.field_id)
        if not field:
            continue

        if y.crop not in crop_data:
            crop_data[y.crop] = {
                'total_yield_kg': 0.0,
                'total_area_ha': 0.0,
                'field_ids': set()
            }

        crop_data[y.crop]['total_yield_kg'] += y.yield_kg
        crop_data[y.crop]['total_area_ha'] += field.area_ha
        crop_data[y.crop]['field_ids'].add(y.field_id)

    # レスポンス構築
    crops = []
    total_yield_kg = 0.0
    total_area_ha = 0.0

    for crop_name, data in sorted(crop_data.items()):
        yield_per_ha = data['total_yield_kg'] / data['total_area_ha'] if data['total_area_ha'] > 0 else 0.0
        crops.append(CropYieldSummaryItem(
            crop=crop_name,
            total_yield_kg=round(data['total_yield_kg'], 2),
            total_area_ha=round(data['total_area_ha'], 2),
            yield_per_ha=round(yield_per_ha, 2),
            field_count=len(data['field_ids'])
        ))
        total_yield_kg += data['total_yield_kg']
        total_area_ha += data['total_area_ha']

    return YearSummaryResponse(
        year=year,
        total_yield_kg=round(total_yield_kg, 2),
        total_area_ha=round(total_area_ha, 2),
        crops=crops
    )


@router.get("/summary/by-crop/{crop}", response_model=CropYieldTrendResponse)
def get_yield_trend_by_crop(
    crop: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    """
    作物別収量推移を取得する。

    指定作物の年別収量推移を返す。
    認証必須。自分のほ場の記録のみ集計。
    """
    user_field_ids = get_user_field_ids(db, current_user.id)

    if not user_field_ids:
        return CropYieldTrendResponse(crop=crop, years=[])

    # ほ場情報を取得
    fields_map = {
        f.id: f for f in db.query(Field).filter(Field.id.in_(user_field_ids)).all()
    }

    # 指定作物の収量を取得
    yields = db.query(Yield).filter(
        Yield.field_id.in_(user_field_ids),
        Yield.crop == crop
    ).order_by(Yield.year).all()

    # 年別に集計
    year_data = {}
    for y in yields:
        field = fields_map.get(y.field_id)
        if not field:
            continue

        if y.year not in year_data:
            year_data[y.year] = {
                'total_yield_kg': 0.0,
                'total_area_ha': 0.0,
                'field_ids': set()
            }

        year_data[y.year]['total_yield_kg'] += y.yield_kg
        year_data[y.year]['total_area_ha'] += field.area_ha
        year_data[y.year]['field_ids'].add(y.field_id)

    # レスポンス構築
    years = []
    for year, data in sorted(year_data.items()):
        yield_per_ha = data['total_yield_kg'] / data['total_area_ha'] if data['total_area_ha'] > 0 else 0.0
        years.append(YearYieldItem(
            year=year,
            total_yield_kg=round(data['total_yield_kg'], 2),
            total_area_ha=round(data['total_area_ha'], 2),
            yield_per_ha=round(yield_per_ha, 2),
            field_count=len(data['field_ids'])
        ))

    return CropYieldTrendResponse(crop=crop, years=years)


@router.get("/stats/{field_id}", response_model=FieldStatsResponse)
def get_field_stats(
    field_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    """
    ほ場別統計を取得する。

    指定ほ場の過去の収量履歴と平均反収を返す。
    認証必須。自分のほ場のみ取得可能。
    """
    field = verify_field_ownership(db, field_id, current_user.id)

    # 収量履歴を取得
    yields = db.query(Yield).filter(
        Yield.field_id == field_id
    ).order_by(Yield.year.desc()).all()

    # 履歴リストと平均反収を計算
    history = []
    total_yield_per_ha = 0.0

    for y in yields:
        yield_per_ha = y.yield_kg / field.area_ha if field.area_ha > 0 else 0.0
        history.append(FieldYieldHistoryItem(
            yield_id=y.id,
            year=y.year,
            crop=y.crop,
            yield_kg=round(y.yield_kg, 2),
            yield_per_ha=round(yield_per_ha, 2),
            notes=y.notes
        ))
        total_yield_per_ha += yield_per_ha

    avg_yield_per_ha = total_yield_per_ha / len(yields) if yields else 0.0

    return FieldStatsResponse(
        field_id=field_id,
        field_name=field.field_name,
        area_ha=field.area_ha,
        total_records=len(yields),
        avg_yield_per_ha=round(avg_yield_per_ha, 2),
        history=history
    )


@router.get("/{yield_id}", response_model=YieldResponse)
def get_yield(
    yield_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    """
    収量記録の詳細を取得する。

    認証必須。自分のほ場の記録のみ取得可能。
    """
    yield_record = verify_yield_ownership(db, yield_id, current_user.id)
    return yield_record


@router.put("/{yield_id}", response_model=YieldResponse)
def update_yield(
    yield_id: int,
    yield_data: YieldUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    """
    収量記録を更新する。

    認証必須。自分のほ場の記録のみ更新可能。
    """
    yield_record = verify_yield_ownership(db, yield_id, current_user.id)

    update_data = yield_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(yield_record, key, value)

    db.commit()
    db.refresh(yield_record)

    return yield_record


@router.delete("/{yield_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_yield(
    yield_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    """
    収量記録を削除する。

    認証必須。自分のほ場の記録のみ削除可能。
    """
    yield_record = verify_yield_ownership(db, yield_id, current_user.id)

    db.delete(yield_record)
    db.commit()

    return None
