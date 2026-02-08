"""
農薬管理API - FastAPI Router
=============================
農薬使用履歴・発注計算・防除マスタ管理のエンドポイントを提供する。
"""

from datetime import date, datetime
from typing import List, Optional, Dict, Any
import json

from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from db_schema import (
    PesticideUsage,
    PesticideUsageCreate,
    PesticideUsageUpdate,
    PesticideUsageResponse,
    Field as FieldModel,
    get_db_context,
)

# api_base.py からインポート（認証用）
# 注: 実際のプロジェクト構成に合わせて調整が必要な場合あり
try:
    from api_base import get_current_user, get_db
except ImportError:
    # フォールバック（テスト用）
    def get_db():
        from db_schema import SessionLocal
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    def get_current_user():
        raise NotImplementedError("認証モジュールが必要です")


# =============================================================================
# Router設定
# =============================================================================
router = APIRouter(prefix="/api", tags=["pesticide"])


# =============================================================================
# 定数（pesticide_order.py から移植）
# =============================================================================

# 単位変換係数（基準単位への変換）
UNIT_CONVERSION = {
    'L': 1000,      # L -> mL
    'l': 1000,
    'mL': 1,        # mL (基準)
    'ml': 1,
    'kg': 1000,     # kg -> g
    'g': 1,         # g (基準)
}

# 散布基準: 10a あたり 100L
SPRAY_VOLUME_PER_10A = 100  # L

# 作物名の正規化マッピング
CROP_NORMALIZE = {
    "てんさい": "てんさい",
    "ビート": "てんさい",
    "甜菜": "てんさい",
    "大豆": "大豆",
    "春小麦": "春小麦",
    "秋小麦": "秋小麦",
    "デントコーン": "デントコーン",
    "コーン": "デントコーン",
    "WCS": "WCS",
    "馬鈴薯": "馬鈴薯",
    "ばれいしょ": "馬鈴薯",
}


# =============================================================================
# Pydanticスキーマ（API用）
# =============================================================================

class CropAreaItem(BaseModel):
    """作物面積アイテム"""
    crop: str = Field(..., description="作物名")
    area_ha: float = Field(..., gt=0, description="面積（ヘクタール）")


class PesticideMasterItem(BaseModel):
    """防除マスタの1レコード"""
    crop: str = Field(..., description="作物名")
    pesticide_name: str = Field(..., description="農薬名")
    month: int = Field(..., ge=1, le=12, description="散布月")
    target: Optional[str] = Field(None, description="対象病害虫")
    dilution_rate: Optional[float] = Field(None, description="希釈倍率")
    amount_per_10a: Optional[float] = Field(None, description="10aあたり使用量")
    unit: Optional[str] = Field("mL", description="単位")


class CalculateOrderRequest(BaseModel):
    """農薬必要量計算リクエスト"""
    crop_areas: List[CropAreaItem] = Field(..., description="作物別面積リスト")
    master_data: Optional[List[PesticideMasterItem]] = Field(
        None,
        description="防除マスタデータ（省略時はデフォルトマスタ使用）"
    )


class PesticideRequirement(BaseModel):
    """農薬必要量レスポンスアイテム"""
    pesticide_name: str
    amount: float = Field(..., description="必要量（表示単位）")
    amount_base: float = Field(..., description="必要量（基準単位: mL or g）")
    unit: str = Field(..., description="表示単位")
    target_crops: List[str] = Field(default_factory=list, description="対象作物")
    targets: List[str] = Field(default_factory=list, description="対象病害虫")


class CalculateOrderResponse(BaseModel):
    """農薬必要量計算レスポンス"""
    requirements: List[PesticideRequirement]
    total_area_ha: float
    crop_summary: Dict[str, float] = Field(..., description="作物別面積サマリ")


class InventoryItem(BaseModel):
    """在庫アイテム"""
    pesticide_name: str
    amount: float = Field(..., description="在庫量")
    unit: str = Field(..., description="単位")


class CalculateWithInventoryRequest(BaseModel):
    """在庫差引計算リクエスト"""
    required_amounts: List[PesticideRequirement] = Field(..., description="必要量リスト")
    inventory: List[InventoryItem] = Field(..., description="在庫リスト")


class OrderItem(BaseModel):
    """発注アイテム"""
    pesticide_name: str
    required_amount: float = Field(..., description="必要量")
    inventory_amount: float = Field(..., description="在庫量")
    order_amount: float = Field(..., description="発注量")
    unit: str


class CalculateWithInventoryResponse(BaseModel):
    """在庫差引計算レスポンス"""
    orders: List[OrderItem]
    total_items: int
    items_to_order: int = Field(..., description="発注が必要な品目数")


class PesticideMasterResponse(BaseModel):
    """防除マスタレスポンス"""
    items: List[PesticideMasterItem]
    count: int


class PesticideMasterUpdateRequest(BaseModel):
    """防除マスタ更新リクエスト"""
    items: List[PesticideMasterItem]


# =============================================================================
# ヘルパー関数
# =============================================================================

def normalize_crop(crop: str) -> str:
    """作物名を正規化"""
    if not crop or crop.strip() == '':
        return ''
    crop_str = crop.strip()
    return CROP_NORMALIZE.get(crop_str, crop_str)


def convert_to_base_unit(amount: float, unit: str) -> float:
    """指定単位から基準単位（mL or g）に変換"""
    conversion = UNIT_CONVERSION.get(unit, 1)
    return amount * conversion


def convert_from_base_unit(amount_base: float, target_unit: str) -> float:
    """基準単位から指定単位に変換"""
    conversion = UNIT_CONVERSION.get(target_unit, 1)
    return amount_base / conversion


def get_display_unit_and_amount(amount_base: float, base_unit: str) -> tuple:
    """基準単位の量を適切な表示単位に変換"""
    if base_unit in ['mL', 'ml'] and amount_base >= 1000:
        return amount_base / 1000, 'L'
    elif base_unit in ['g'] and amount_base >= 1000:
        return amount_base / 1000, 'kg'
    return amount_base, base_unit


def check_field_ownership(db: Session, field_id: int, user) -> FieldModel:
    """ほ場の所有権を確認"""
    field = db.query(FieldModel).filter(FieldModel.id == field_id).first()
    if not field:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"ほ場が見つかりません: {field_id}"
        )
    # user.id または user.farmer_id で所有権確認（モデル構成に依存）
    farmer_id = getattr(user, 'farmer_id', None) or getattr(user, 'id', None)
    if field.farmer_id != farmer_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="このほ場へのアクセス権限がありません"
        )
    return field


# =============================================================================
# デフォルト防除マスタ（インメモリ）
# 本番環境ではDB or ファイルから読み込む
# =============================================================================
DEFAULT_PESTICIDE_MASTER: List[Dict[str, Any]] = []


def get_default_master() -> List[Dict[str, Any]]:
    """デフォルト防除マスタを取得"""
    global DEFAULT_PESTICIDE_MASTER
    return DEFAULT_PESTICIDE_MASTER


def set_default_master(items: List[Dict[str, Any]]):
    """デフォルト防除マスタを設定"""
    global DEFAULT_PESTICIDE_MASTER
    DEFAULT_PESTICIDE_MASTER = items


# =============================================================================
# 農薬使用履歴API
# =============================================================================

@router.post("/pesticide-usage", response_model=PesticideUsageResponse, status_code=status.HTTP_201_CREATED)
def create_pesticide_usage(
    usage: PesticideUsageCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    農薬使用記録を登録

    自分のほ場に対してのみ登録可能。
    """
    # 所有権確認
    check_field_ownership(db, usage.field_id, current_user)

    # レコード作成
    db_usage = PesticideUsage(
        field_id=usage.field_id,
        date=usage.date,
        pesticide_name=usage.pesticide_name,
        amount=usage.amount,
        unit=usage.unit,
        target=usage.target,
        weather=usage.weather,
        notes=usage.notes,
    )
    db.add(db_usage)
    db.commit()
    db.refresh(db_usage)

    return db_usage


@router.get("/pesticide-usage", response_model=List[PesticideUsageResponse])
def list_pesticide_usage(
    field_id: Optional[int] = Query(None, description="ほ場IDでフィルタ"),
    date_from: Optional[date] = Query(None, description="開始日（この日以降）"),
    date_to: Optional[date] = Query(None, description="終了日（この日以前）"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    農薬使用履歴一覧を取得

    自分のほ場の記録のみ取得可能。
    """
    # ユーザーのほ場IDを取得
    farmer_id = getattr(current_user, 'farmer_id', None) or getattr(current_user, 'id', None)
    user_field_ids = [f.id for f in db.query(FieldModel).filter(FieldModel.farmer_id == farmer_id).all()]

    if not user_field_ids:
        return []

    # クエリ構築
    query = db.query(PesticideUsage).filter(PesticideUsage.field_id.in_(user_field_ids))

    if field_id is not None:
        if field_id not in user_field_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="このほ場へのアクセス権限がありません"
            )
        query = query.filter(PesticideUsage.field_id == field_id)

    if date_from is not None:
        query = query.filter(PesticideUsage.date >= date_from)

    if date_to is not None:
        query = query.filter(PesticideUsage.date <= date_to)

    query = query.order_by(PesticideUsage.date.desc())

    return query.all()


@router.get("/pesticide-usage/{usage_id}", response_model=PesticideUsageResponse)
def get_pesticide_usage(
    usage_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    農薬使用記録の詳細を取得
    """
    usage = db.query(PesticideUsage).filter(PesticideUsage.id == usage_id).first()
    if not usage:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"使用記録が見つかりません: {usage_id}"
        )

    # 所有権確認
    check_field_ownership(db, usage.field_id, current_user)

    return usage


@router.put("/pesticide-usage/{usage_id}", response_model=PesticideUsageResponse)
def update_pesticide_usage(
    usage_id: int,
    update_data: PesticideUsageUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    農薬使用記録を更新
    """
    usage = db.query(PesticideUsage).filter(PesticideUsage.id == usage_id).first()
    if not usage:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"使用記録が見つかりません: {usage_id}"
        )

    # 所有権確認
    check_field_ownership(db, usage.field_id, current_user)

    # 更新
    update_dict = update_data.model_dump(exclude_unset=True)
    for key, value in update_dict.items():
        setattr(usage, key, value)

    db.commit()
    db.refresh(usage)

    return usage


@router.delete("/pesticide-usage/{usage_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_pesticide_usage(
    usage_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    農薬使用記録を削除
    """
    usage = db.query(PesticideUsage).filter(PesticideUsage.id == usage_id).first()
    if not usage:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"使用記録が見つかりません: {usage_id}"
        )

    # 所有権確認
    check_field_ownership(db, usage.field_id, current_user)

    db.delete(usage)
    db.commit()

    return None


# =============================================================================
# 農薬発注計算API
# =============================================================================

@router.post("/pesticide/calculate-order", response_model=CalculateOrderResponse)
def calculate_pesticide_order(
    request: CalculateOrderRequest,
    current_user = Depends(get_current_user)
):
    """
    農薬必要量を計算

    作物別面積と防除マスタから、必要な農薬量を算出する。
    """
    # 作物面積を正規化して集計
    crop_areas: Dict[str, float] = {}
    for item in request.crop_areas:
        normalized = normalize_crop(item.crop)
        if normalized:
            crop_areas[normalized] = crop_areas.get(normalized, 0) + item.area_ha

    if not crop_areas:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="有効な作物データがありません"
        )

    # マスタデータ取得
    if request.master_data:
        master_items = [item.model_dump() for item in request.master_data]
    else:
        master_items = get_default_master()

    if not master_items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="防除マスタデータがありません。master_dataを指定するか、マスタを設定してください。"
        )

    # 農薬必要量を計算
    pesticide_totals: Dict[str, Dict[str, Any]] = {}

    for crop, area_ha in crop_areas.items():
        # このクロップのマスタデータを取得
        crop_master = [m for m in master_items if normalize_crop(m.get('crop', '')) == crop]

        area_10a = area_ha * 10  # haを10a単位に変換

        for prow in crop_master:
            pesticide = prow.get('pesticide_name', '')
            dilution = prow.get('dilution_rate')
            amount_per_10a = prow.get('amount_per_10a')
            unit = prow.get('unit', 'mL')
            target = prow.get('target', '')

            # 必要量を計算
            amount = 0.0
            final_unit = 'mL'

            if amount_per_10a is not None and str(amount_per_10a).strip() != '':
                # 直接指定（mL/10a, g/10a など）
                try:
                    amount = float(amount_per_10a) * area_10a
                    final_unit = str(unit) if unit else 'mL'
                except (ValueError, TypeError):
                    continue
            elif dilution is not None and str(dilution).strip() != '':
                # 希釈倍率指定 → 100L/10a 基準で計算
                try:
                    dilution_rate = float(dilution)
                    # 100L/10a ÷ 希釈倍率 × 面積(10a)
                    amount = (SPRAY_VOLUME_PER_10A / dilution_rate) * area_10a * 1000  # mL
                    final_unit = 'mL'
                except (ValueError, TypeError, ZeroDivisionError):
                    continue
            else:
                continue

            # 集計
            if pesticide not in pesticide_totals:
                pesticide_totals[pesticide] = {
                    'amount_base': 0.0,
                    'unit': final_unit,
                    'crops': set(),
                    'targets': set()
                }

            # 基準単位に変換して加算
            amount_base = convert_to_base_unit(amount, final_unit)
            pesticide_totals[pesticide]['amount_base'] += amount_base
            pesticide_totals[pesticide]['crops'].add(crop)
            if target:
                pesticide_totals[pesticide]['targets'].add(str(target))

    # レスポンス構築
    requirements = []
    for pesticide, data in sorted(pesticide_totals.items()):
        amount_base = data['amount_base']
        base_unit = data['unit']

        # 表示用単位に変換
        amount_display, display_unit = get_display_unit_and_amount(amount_base, base_unit)

        requirements.append(PesticideRequirement(
            pesticide_name=pesticide,
            amount=round(amount_display, 2),
            amount_base=round(amount_base, 2),
            unit=display_unit,
            target_crops=sorted(list(data['crops'])),
            targets=sorted(list(data['targets']))
        ))

    return CalculateOrderResponse(
        requirements=requirements,
        total_area_ha=sum(crop_areas.values()),
        crop_summary=crop_areas
    )


@router.post("/pesticide/calculate-with-inventory", response_model=CalculateWithInventoryResponse)
def calculate_with_inventory(
    request: CalculateWithInventoryRequest,
    current_user = Depends(get_current_user)
):
    """
    在庫を差し引いた発注量を計算

    必要量から在庫を引いて、発注が必要な量を算出する。
    """
    # 在庫を辞書化（基準単位で保持）
    inventory_map: Dict[str, tuple] = {}
    for inv in request.inventory:
        amount_base = convert_to_base_unit(inv.amount, inv.unit)
        inventory_map[inv.pesticide_name] = (amount_base, inv.unit)

    orders = []
    items_to_order = 0

    for req in request.required_amounts:
        inv_amount_base = 0.0
        inv_unit = req.unit

        if req.pesticide_name in inventory_map:
            inv_amount_base, inv_unit = inventory_map[req.pesticide_name]

        # 表示用単位で計算
        req_amount = req.amount
        inv_amount_display, _ = get_display_unit_and_amount(inv_amount_base, 'mL' if req.unit in ['L', 'mL', 'ml'] else 'g')

        # 単位を揃える
        if req.unit == 'L' and inv_unit in ['mL', 'ml']:
            inv_amount_display = inv_amount_base / 1000
        elif req.unit == 'kg' and inv_unit == 'g':
            inv_amount_display = inv_amount_base / 1000
        elif req.unit in ['mL', 'ml']:
            inv_amount_display = inv_amount_base
        elif req.unit == 'g':
            inv_amount_display = inv_amount_base
        else:
            inv_amount_display = convert_from_base_unit(inv_amount_base, req.unit)

        # 発注量 = max(0, 必要量 - 在庫)
        order_amount = max(0, req_amount - inv_amount_display)

        if order_amount > 0:
            items_to_order += 1

        orders.append(OrderItem(
            pesticide_name=req.pesticide_name,
            required_amount=round(req_amount, 2),
            inventory_amount=round(inv_amount_display, 2),
            order_amount=round(order_amount, 2),
            unit=req.unit
        ))

    return CalculateWithInventoryResponse(
        orders=orders,
        total_items=len(orders),
        items_to_order=items_to_order
    )


# =============================================================================
# 防除マスタAPI
# =============================================================================

@router.get("/pesticide/master", response_model=PesticideMasterResponse)
def get_pesticide_master(
    current_user = Depends(get_current_user)
):
    """
    防除マスタを取得
    """
    master_items = get_default_master()

    items = [
        PesticideMasterItem(
            crop=item.get('crop', ''),
            pesticide_name=item.get('pesticide_name', ''),
            month=item.get('month', 1),
            target=item.get('target'),
            dilution_rate=item.get('dilution_rate'),
            amount_per_10a=item.get('amount_per_10a'),
            unit=item.get('unit', 'mL')
        )
        for item in master_items
    ]

    return PesticideMasterResponse(
        items=items,
        count=len(items)
    )


@router.put("/pesticide/master", response_model=PesticideMasterResponse)
def update_pesticide_master(
    request: PesticideMasterUpdateRequest,
    current_user = Depends(get_current_user)
):
    """
    防除マスタを更新（管理者用）

    注: 本番環境では管理者権限チェックを追加すること
    """
    # マスタを更新
    new_items = [item.model_dump() for item in request.items]
    set_default_master(new_items)

    return PesticideMasterResponse(
        items=request.items,
        count=len(request.items)
    )
