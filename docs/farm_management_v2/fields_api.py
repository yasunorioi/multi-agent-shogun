"""
農業管理アプリ v2.0 - ほ場登録API
==================================
ほ場のCRUD操作、面積計算、住所検索を提供するFastAPI Router。
"""

from typing import List, Optional

import requests
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from pyproj import Geod
from sqlalchemy.orm import Session

from api_base import get_current_user, get_db
from db_schema import Field, FieldCreate, FieldUpdate, FieldResponse, User


# =============================================================================
# ルーター設定
# =============================================================================
router = APIRouter(prefix="/api/fields", tags=["fields"])


# =============================================================================
# 追加のPydanticスキーマ
# =============================================================================
class PolygonCoordinate(BaseModel):
    """ポリゴンの座標（緯度、経度）"""
    lat: float
    lng: float


class CalculateAreaRequest(BaseModel):
    """面積計算リクエスト（GeoJSON形式）"""
    type: str = "Polygon"
    coordinates: List[List[List[float]]]  # [[[lng, lat], [lng, lat], ...]]


class CalculateAreaResponse(BaseModel):
    """面積計算レスポンス"""
    area_ha: float
    area_a: float
    area_m2: float


class GeocodeResponse(BaseModel):
    """住所検索レスポンス"""
    lat: float
    lng: float
    display_name: str


# =============================================================================
# 定数
# =============================================================================
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"


# =============================================================================
# ヘルパー関数
# =============================================================================
def calculate_area_from_geojson(coordinates: List[List[List[float]]]) -> float:
    """
    GeoJSON形式の座標から面積を計算（平方メートル）
    WGS84楕円体上の面積を正確に計算

    Args:
        coordinates: GeoJSON形式 [[[lng, lat], [lng, lat], ...]]

    Returns:
        面積（平方メートル）
    """
    if not coordinates or not coordinates[0] or len(coordinates[0]) < 3:
        return 0.0

    ring = coordinates[0]  # 外環のみ使用

    # Geod（測地線計算）を使用
    geod = Geod(ellps="WGS84")

    lons = [coord[0] for coord in ring]
    lats = [coord[1] for coord in ring]

    # polygon_area_perimeter は (面積, 周長) を返す
    area_m2, _ = geod.polygon_area_perimeter(lons, lats)

    return abs(area_m2)


def get_field_or_404(db: Session, field_id: int, user: User) -> Field:
    """
    ほ場を取得。存在しないか権限がない場合は404を返す。
    """
    field = db.query(Field).filter(Field.id == field_id).first()

    if not field:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"ほ場ID {field_id} が見つかりません"
        )

    # 権限チェック: 自分のほ場のみ操作可能
    if field.farmer_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="このほ場にアクセスする権限がありません"
        )

    return field


# =============================================================================
# CRUDエンドポイント
# =============================================================================
@router.post("", response_model=FieldResponse, status_code=status.HTTP_201_CREATED)
def create_field(
    field_data: FieldCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    ほ場を登録

    新しいほ場を作成し、登録情報を返す。
    farmer_id は認証済みユーザーのIDに自動設定される。
    """
    # farmer_id を認証ユーザーのIDで上書き（セキュリティのため）
    field = Field(
        farmer_id=current_user.id,
        field_name=field_data.field_name,
        district=field_data.district,
        area_ha=field_data.area_ha,
        polygon_geojson=field_data.polygon_geojson,
        beet_forbidden=field_data.beet_forbidden
    )

    db.add(field)
    db.commit()
    db.refresh(field)

    return field


@router.get("", response_model=List[FieldResponse])
def list_fields(
    farmer_id: Optional[int] = Query(None, description="農家IDでフィルタ（省略時は自分のほ場のみ）"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    ほ場一覧を取得

    認証済みユーザーのほ場一覧を返す。
    farmer_id パラメータが指定されても、自分のほ場のみ取得可能。
    """
    # 自分のほ場のみ取得可能
    query = db.query(Field).filter(Field.farmer_id == current_user.id)

    fields = query.order_by(Field.created_at.desc()).all()

    return fields


@router.get("/{field_id}", response_model=FieldResponse)
def get_field(
    field_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    ほ場詳細を取得

    指定されたIDのほ場情報を返す。
    自分のほ場のみ取得可能。
    """
    return get_field_or_404(db, field_id, current_user)


@router.put("/{field_id}", response_model=FieldResponse)
def update_field(
    field_id: int,
    field_data: FieldUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    ほ場を更新

    指定されたIDのほ場情報を更新する。
    自分のほ場のみ更新可能。
    """
    field = get_field_or_404(db, field_id, current_user)

    # 指定されたフィールドのみ更新
    update_data = field_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(field, key, value)

    db.commit()
    db.refresh(field)

    return field


@router.delete("/{field_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_field(
    field_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    ほ場を削除

    指定されたIDのほ場を削除する。
    自分のほ場のみ削除可能。
    """
    field = get_field_or_404(db, field_id, current_user)

    db.delete(field)
    db.commit()

    return None


# =============================================================================
# 特殊機能エンドポイント
# =============================================================================
@router.post("/calculate-area", response_model=CalculateAreaResponse)
def calculate_area(
    polygon: CalculateAreaRequest,
    current_user: User = Depends(get_current_user)
):
    """
    ポリゴンから面積を計算

    GeoJSON形式のポリゴン座標を受け取り、面積を返す。
    WGS84楕円体上の正確な面積を計算。

    リクエスト例:
    ```json
    {
        "type": "Polygon",
        "coordinates": [[[141.35, 43.06], [141.36, 43.06], [141.36, 43.07], [141.35, 43.07], [141.35, 43.06]]]
    }
    ```
    """
    if polygon.type != "Polygon":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="GeoJSONのtypeは'Polygon'である必要があります"
        )

    if not polygon.coordinates or not polygon.coordinates[0]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="座標データが空です"
        )

    if len(polygon.coordinates[0]) < 4:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ポリゴンには最低4点（始点=終点を含む）が必要です"
        )

    area_m2 = calculate_area_from_geojson(polygon.coordinates)
    area_a = area_m2 / 100.0
    area_ha = area_m2 / 10000.0

    return CalculateAreaResponse(
        area_ha=round(area_ha, 4),
        area_a=round(area_a, 2),
        area_m2=round(area_m2, 2)
    )


# 住所検索用ルーター（/api/geocode）
geocode_router = APIRouter(prefix="/api", tags=["geocode"])


@geocode_router.get("/geocode", response_model=GeocodeResponse)
def geocode(
    q: str = Query(..., description="検索する住所文字列", min_length=1),
    current_user: User = Depends(get_current_user)
):
    """
    住所検索（ジオコーディング）

    住所・地名からNominatim APIで座標を検索する。

    クエリパラメータ:
    - q: 検索する住所文字列（例: "札幌市", "十勝", "美瑛町"）
    """
    try:
        params = {
            "q": q,
            "format": "json",
            "limit": 1,
            "countrycodes": "jp",
        }
        headers = {
            "User-Agent": "FarmManagementApp/2.0"
        }

        response = requests.get(
            NOMINATIM_URL,
            params=params,
            headers=headers,
            timeout=10
        )
        response.raise_for_status()

        results = response.json()

        if not results:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"「{q}」の検索結果が見つかりません"
            )

        result = results[0]
        return GeocodeResponse(
            lat=float(result["lat"]),
            lng=float(result["lon"]),
            display_name=result.get("display_name", q)
        )

    except requests.exceptions.Timeout:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="住所検索がタイムアウトしました"
        )
    except requests.exceptions.RequestException as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"住所検索サービスへの接続に失敗しました: {str(e)}"
        )
