"""
農業管理アプリ v2.0 - 統合エントリポイント
==========================================
全APIルーターを統合し、単一のエントリポイントとして起動できるようにする。

起動方法:
    cd /home/yasu/multi-agent-shogun/docs/farm_management_v2
    uvicorn main:app --reload --host 0.0.0.0 --port 8000

API ドキュメント:
    http://localhost:8000/docs (Swagger UI)
    http://localhost:8000/redoc (ReDoc)
"""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# -----------------------------------------------------------------------------
# データベース・認証基盤のインポート
# -----------------------------------------------------------------------------
from db_schema import Base, engine

# -----------------------------------------------------------------------------
# 各APIルーターのインポート
# -----------------------------------------------------------------------------
# 認証API (api_base.py からは app ではなく router 相当のエンドポイントを含む app を使用)
# 方針: api_base.py の app を直接使わず、新規 app を作成して router を include する
from api_base import (
    app as auth_app,  # 認証エンドポイント参照用
    get_db,
    get_current_user,
    oauth2_scheme,
)

# ほ場API
from fields_api import router as fields_router, geocode_router

# 作付計画API
from crop_plans_api import router as crop_plans_router

# 農薬API
from pesticide_api import router as pesticide_router

# 収量API（足軽6が作成中のため、import エラーにならないよう try-except で対応）
try:
    from yields_api import router as yields_router
    YIELDS_API_AVAILABLE = True
except ImportError:
    yields_router = None
    YIELDS_API_AVAILABLE = False
    logging.warning("yields_api.py が見つかりません。収量APIは無効です。")


# =============================================================================
# FastAPI アプリケーション（統合版）
# =============================================================================
app = FastAPI(
    title="農業管理アプリ v2.0 API",
    description="""
農業管理の統合API

## 機能一覧

### 認証 (`/auth`)
- ユーザー登録・ログイン・ログアウト
- JWT トークンベース認証

### ほ場管理 (`/api/fields`)
- ほ場の CRUD 操作
- GeoJSON ポリゴンによる面積計算
- 住所からの座標検索（ジオコーディング）

### 作付計画 (`/api/crop-plans`)
- 輪作計画の CRUD 操作
- 一括登録・年別一覧
- 輪作最適化（将来拡張）

### 農薬管理 (`/api/pesticide-usage`, `/api/pesticide`)
- 農薬使用履歴の CRUD
- 必要量計算・在庫差引計算
- 防除マスタ管理

### 収量記録 (`/api/yields`)
- 収量記録の CRUD（準備中）
""",
    version="2.0.0",
    contact={
        "name": "農業管理アプリ開発チーム",
    },
    license_info={
        "name": "Private",
    },
)


# =============================================================================
# CORS ミドルウェア設定
# =============================================================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 本番環境では適切なオリジンに制限すること
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# 起動時イベント
# =============================================================================
@app.on_event("startup")
def on_startup():
    """
    アプリケーション起動時にデータベースを初期化
    """
    Base.metadata.create_all(bind=engine)
    logging.info("Database initialized successfully.")

    if not YIELDS_API_AVAILABLE:
        logging.warning("Yields API is not available. Please ensure yields_api.py exists.")


# =============================================================================
# 認証エンドポイントの移植
# =============================================================================
# api_base.py の認証エンドポイントを直接参照するため、
# そのルートを include する代わりに、api_base.app のルートをコピー
#
# 方法: api_base.py のエンドポイントを手動で追加するか、
#       api_base.app のルートを動的に追加
#
# ここでは api_base.app のルートを動的に main app に追加
for route in auth_app.routes:
    app.routes.append(route)


# =============================================================================
# 各 API ルーターの登録
# =============================================================================

# ほ場API
app.include_router(fields_router)
app.include_router(geocode_router)

# 作付計画API
app.include_router(crop_plans_router)

# 農薬API
app.include_router(pesticide_router)

# 収量API（利用可能な場合のみ）
if YIELDS_API_AVAILABLE and yields_router is not None:
    app.include_router(yields_router)


# =============================================================================
# ルートエンドポイント
# =============================================================================
@app.get("/", tags=["root"])
def root():
    """
    ルートエンドポイント - API 情報を返す
    """
    return {
        "name": "農業管理アプリ v2.0 API",
        "version": "2.0.0",
        "docs": "/docs",
        "redoc": "/redoc",
        "health": "/health",
        "endpoints": {
            "auth": "/auth/*",
            "fields": "/api/fields/*",
            "geocode": "/api/geocode",
            "crop_plans": "/api/crop-plans/*",
            "pesticide_usage": "/api/pesticide-usage/*",
            "pesticide": "/api/pesticide/*",
            "yields": "/api/yields/*" if YIELDS_API_AVAILABLE else "(not available)",
        }
    }


# =============================================================================
# 起動方法（直接実行時）
# =============================================================================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
