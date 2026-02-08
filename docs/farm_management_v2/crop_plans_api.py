"""
農業管理アプリ v2.0 - 作付計画API
==================================
輪作計画のCRUD操作と一括登録機能を提供する。

エンドポイント一覧:
  CRUD操作:
    POST   /api/crop-plans              - 作付計画登録
    GET    /api/crop-plans              - 作付計画一覧取得
    GET    /api/crop-plans/{plan_id}    - 作付計画詳細取得
    PUT    /api/crop-plans/{plan_id}    - 作付計画更新
    DELETE /api/crop-plans/{plan_id}    - 作付計画削除

  一括操作:
    POST   /api/crop-plans/bulk         - 複数ほ場の作付計画を一括登録
    GET    /api/crop-plans/by-year/{year} - 年別の全ほ場作付一覧

  最適化（将来拡張用）:
    POST   /api/crop-plans/optimize     - 輪作計画最適化（構造のみ）
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db_schema import CropPlan, Field, CropPlanCreate, CropPlanUpdate, CropPlanResponse
from api_base import get_db, get_current_user


# =============================================================================
# Router設定
# =============================================================================
router = APIRouter(prefix="/api/crop-plans", tags=["crop-plans"])


# =============================================================================
# 追加Pydanticスキーマ（一括操作・最適化用）
# =============================================================================
class BulkCropPlanItem(BaseModel):
    """一括登録用の単一アイテム"""
    field_id: int
    year: int
    crop: str


class BulkCropPlanCreate(BaseModel):
    """一括登録リクエスト"""
    plans: List[BulkCropPlanItem]


class BulkCropPlanResponse(BaseModel):
    """一括登録レスポンス"""
    created_count: int
    plans: List[CropPlanResponse]


class CropPlanByYearItem(BaseModel):
    """年別作付一覧の単一アイテム"""
    plan_id: int
    field_id: int
    field_name: str
    district: Optional[str]
    area_ha: float
    crop: str


class CropPlanByYearResponse(BaseModel):
    """年別作付一覧レスポンス"""
    year: int
    total_fields: int
    plans: List[CropPlanByYearItem]


class OptimizeRequest(BaseModel):
    """最適化リクエスト（将来拡張用）"""
    field_ids: List[int]
    target_year: int
    n_years: int = 5


class OptimizeResponse(BaseModel):
    """最適化レスポンス（将来拡張用）"""
    message: str
    status: str


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


def verify_plan_ownership(db: Session, plan_id: int, user_id: int) -> CropPlan:
    """
    作付計画の所有権を検証する。

    Args:
        db: データベースセッション
        plan_id: 作付計画ID
        user_id: ユーザーID（farmer_id）

    Returns:
        CropPlan: 検証済みの作付計画オブジェクト

    Raises:
        HTTPException: 計画が存在しない、または所有権がない場合
    """
    plan = db.query(CropPlan).filter(CropPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"作付計画ID {plan_id} が見つかりません"
        )

    field = db.query(Field).filter(Field.id == plan.field_id).first()
    if not field or field.farmer_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="この作付計画へのアクセス権限がありません"
        )
    return plan


# =============================================================================
# CRUD操作エンドポイント
# =============================================================================
@router.post("", response_model=CropPlanResponse, status_code=status.HTTP_201_CREATED)
def create_crop_plan(
    plan_data: CropPlanCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    作付計画を登録する。

    認証必須。自分のほ場の計画のみ登録可能。
    """
    verify_field_ownership(db, plan_data.field_id, current_user.id)

    existing = db.query(CropPlan).filter(
        CropPlan.field_id == plan_data.field_id,
        CropPlan.year == plan_data.year
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"ほ場ID {plan_data.field_id} の {plan_data.year} 年の計画は既に存在します"
        )

    db_plan = CropPlan(
        field_id=plan_data.field_id,
        year=plan_data.year,
        crop=plan_data.crop
    )
    db.add(db_plan)
    db.commit()
    db.refresh(db_plan)

    return db_plan


@router.get("", response_model=List[CropPlanResponse])
def list_crop_plans(
    field_id: Optional[int] = Query(None, description="ほ場IDでフィルタ"),
    year: Optional[int] = Query(None, description="年でフィルタ"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    作付計画一覧を取得する。

    認証必須。自分のほ場の計画のみ取得可能。
    field_id と year でフィルタ可能。
    """
    user_field_ids = [f.id for f in db.query(Field).filter(Field.farmer_id == current_user.id).all()]

    query = db.query(CropPlan).filter(CropPlan.field_id.in_(user_field_ids))

    if field_id is not None:
        if field_id not in user_field_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="このほ場へのアクセス権限がありません"
            )
        query = query.filter(CropPlan.field_id == field_id)

    if year is not None:
        query = query.filter(CropPlan.year == year)

    plans = query.order_by(CropPlan.year, CropPlan.field_id).all()
    return plans


@router.get("/{plan_id}", response_model=CropPlanResponse)
def get_crop_plan(
    plan_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    作付計画の詳細を取得する。

    認証必須。自分のほ場の計画のみ取得可能。
    """
    plan = verify_plan_ownership(db, plan_id, current_user.id)
    return plan


@router.put("/{plan_id}", response_model=CropPlanResponse)
def update_crop_plan(
    plan_id: int,
    plan_data: CropPlanUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    作付計画を更新する。

    認証必須。自分のほ場の計画のみ更新可能。
    """
    plan = verify_plan_ownership(db, plan_id, current_user.id)

    if plan_data.year is not None and plan_data.year != plan.year:
        existing = db.query(CropPlan).filter(
            CropPlan.field_id == plan.field_id,
            CropPlan.year == plan_data.year,
            CropPlan.id != plan_id
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"ほ場ID {plan.field_id} の {plan_data.year} 年の計画は既に存在します"
            )
        plan.year = plan_data.year

    if plan_data.crop is not None:
        plan.crop = plan_data.crop

    db.commit()
    db.refresh(plan)

    return plan


@router.delete("/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_crop_plan(
    plan_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    作付計画を削除する。

    認証必須。自分のほ場の計画のみ削除可能。
    """
    plan = verify_plan_ownership(db, plan_id, current_user.id)

    db.delete(plan)
    db.commit()

    return None


# =============================================================================
# 一括操作エンドポイント
# =============================================================================
@router.post("/bulk", response_model=BulkCropPlanResponse, status_code=status.HTTP_201_CREATED)
def bulk_create_crop_plans(
    bulk_data: BulkCropPlanCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    複数ほ場の作付計画を一括登録する。

    認証必須。自分のほ場の計画のみ登録可能。
    既存の計画がある場合はスキップせず、エラーを返す。
    """
    if not bulk_data.plans:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="登録する計画がありません"
        )

    user_field_ids = {f.id for f in db.query(Field).filter(Field.farmer_id == current_user.id).all()}

    for item in bulk_data.plans:
        if item.field_id not in user_field_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"ほ場ID {item.field_id} へのアクセス権限がありません"
            )

    for item in bulk_data.plans:
        existing = db.query(CropPlan).filter(
            CropPlan.field_id == item.field_id,
            CropPlan.year == item.year
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"ほ場ID {item.field_id} の {item.year} 年の計画は既に存在します"
            )

    created_plans = []
    for item in bulk_data.plans:
        db_plan = CropPlan(
            field_id=item.field_id,
            year=item.year,
            crop=item.crop
        )
        db.add(db_plan)
        created_plans.append(db_plan)

    db.commit()

    for plan in created_plans:
        db.refresh(plan)

    return BulkCropPlanResponse(
        created_count=len(created_plans),
        plans=created_plans
    )


@router.get("/by-year/{year}", response_model=CropPlanByYearResponse)
def get_crop_plans_by_year(
    year: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    年別の全ほ場作付一覧を取得する。

    認証必須。自分のほ場の計画のみ取得可能。
    ほ場情報（名前、地区、面積）も含めて返す。
    """
    user_fields = db.query(Field).filter(Field.farmer_id == current_user.id).all()
    user_field_map = {f.id: f for f in user_fields}
    user_field_ids = list(user_field_map.keys())

    plans = db.query(CropPlan).filter(
        CropPlan.field_id.in_(user_field_ids),
        CropPlan.year == year
    ).all()

    result_plans = []
    for plan in plans:
        field = user_field_map[plan.field_id]
        result_plans.append(CropPlanByYearItem(
            plan_id=plan.id,
            field_id=plan.field_id,
            field_name=field.field_name,
            district=field.district,
            area_ha=field.area_ha,
            crop=plan.crop
        ))

    result_plans.sort(key=lambda x: (x.district or "", x.field_name))

    return CropPlanByYearResponse(
        year=year,
        total_fields=len(result_plans),
        plans=result_plans
    )


# =============================================================================
# 最適化エンドポイント（将来拡張用）
# =============================================================================
@router.post("/optimize", response_model=OptimizeResponse)
def optimize_crop_plans(
    request: OptimizeRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    輪作計画を最適化する（将来拡張用）。

    現在は構造のみ実装。OR-Tools最適化は後で追加可能。

    認証必須。自分のほ場の計画のみ最適化可能。
    """
    user_field_ids = {f.id for f in db.query(Field).filter(Field.farmer_id == current_user.id).all()}

    for field_id in request.field_ids:
        if field_id not in user_field_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"ほ場ID {field_id} へのアクセス権限がありません"
            )

    return OptimizeResponse(
        message="最適化機能は現在準備中です。将来のバージョンで実装予定です。",
        status="not_implemented"
    )
