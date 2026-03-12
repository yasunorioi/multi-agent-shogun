# Claude Vision 画像解析

Claude Vision APIを使って画像からテキストや情報を抽出するパターン。

## 使用方法

```
/claude-vision-analyzer <画像パス> <抽出したい情報>
```

## 実装パターン

```python
import anthropic
import base64
from pathlib import Path

def analyze_image_with_vision(
    image_path: str,
    prompt: str,
    model: str = "claude-3-haiku-20240307"
) -> str:
    """
    Claude Vision APIで画像を解析

    Args:
        image_path: 画像ファイルパス
        prompt: 抽出したい情報の指示
        model: 使用モデル（コスト考慮でhaiku推奨）

    Returns:
        解析結果テキスト
    """
    client = anthropic.Anthropic()

    # 画像をBase64エンコード
    image_path = Path(image_path)
    with open(image_path, 'rb') as f:
        image_data = base64.standard_b64encode(f.read()).decode('utf-8')

    # MIMEタイプ判定
    suffix = image_path.suffix.lower()
    media_types = {
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.gif': 'image/gif',
        '.webp': 'image/webp'
    }
    media_type = media_types.get(suffix, 'image/jpeg')

    # Vision API呼び出し
    response = client.messages.create(
        model=model,
        max_tokens=1024,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": image_data
                        }
                    },
                    {
                        "type": "text",
                        "text": prompt
                    }
                ]
            }
        ]
    )

    return response.content[0].text
```

## 使用例（農薬ラベル認識）

```python
def extract_pesticide_name(image_path: str) -> str:
    """農薬ラベル画像から農薬名を抽出"""
    prompt = """この画像は農薬のラベルです。
農薬名（商品名）を抽出してください。
農薬名のみを返してください。余計な説明は不要です。
読み取れない場合は「不明」と返してください。"""

    result = analyze_image_with_vision(image_path, prompt)
    return result.strip()

# 使用例
pesticide_name = extract_pesticide_name('photo.jpg')
print(f'認識結果: {pesticide_name}')
```

## EXIF情報の取得

```python
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS

def extract_exif(image_path: str) -> dict:
    """画像からEXIF情報を抽出"""
    img = Image.open(image_path)
    exif_data = img._getexif()

    if not exif_data:
        return {}

    result = {}

    for tag_id, value in exif_data.items():
        tag = TAGS.get(tag_id, tag_id)

        if tag == 'GPSInfo':
            gps = {}
            for gps_tag_id, gps_value in value.items():
                gps_tag = GPSTAGS.get(gps_tag_id, gps_tag_id)
                gps[gps_tag] = gps_value
            result['GPSInfo'] = gps
        elif tag == 'DateTimeOriginal':
            result['datetime'] = value
        else:
            result[tag] = value

    return result

def get_gps_coordinates(exif: dict) -> tuple:
    """EXIF情報から緯度経度を取得"""
    gps = exif.get('GPSInfo', {})
    if not gps:
        return None, None

    def convert_to_degrees(value):
        d, m, s = value
        return d + (m / 60.0) + (s / 3600.0)

    lat = gps.get('GPSLatitude')
    lat_ref = gps.get('GPSLatitudeRef')
    lon = gps.get('GPSLongitude')
    lon_ref = gps.get('GPSLongitudeRef')

    if lat and lon:
        lat_deg = convert_to_degrees(lat)
        lon_deg = convert_to_degrees(lon)
        if lat_ref == 'S':
            lat_deg = -lat_deg
        if lon_ref == 'W':
            lon_deg = -lon_deg
        return lat_deg, lon_deg

    return None, None
```

## 注意事項

- anthropicパッケージが必要（`pip install anthropic`）
- ANTHROPIC_API_KEY環境変数が必要
- コスト考慮でclaude-3-haiku推奨（大量処理時）
- 画像サイズが大きい場合はリサイズ推奨
