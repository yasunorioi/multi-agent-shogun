---
name: emergency-sensor-handler
description: |
  降雨で灌水を即停止したい時、強風で窓を緊急閉鎖したい時。
  Pico W/RPiでIRQ割り込みや高速ポーリング(100ms以下)の緊急センサーを実装する時。
  通常センサー(UECS 10秒間隔)では間に合わない即時制御が必要な時。
agent: 足軽
---

# Emergency Sensor Handler — 緊急センサー高速検知

通常のUECS CCM(10秒間隔)では間に合わない緊急停止をIRQ割り込みまたは高速ポーリングで実現する。

## When to Use

- 降雨検知→灌水即停止が必要
- 強風検知→側窓緊急閉鎖が必要
- 煙・扉開閉など1ms以下の応答が必要
- 通常センサー経路(UECS CCM)とは別系統で安全機構を構築したい

## Instructions

### Step 1: センサー種別と検知方式を選択

| センサー | 方式 | 応答時間 |
|---------|------|---------|
| 降雨(デジタル) | IRQ割り込み | < 1ms |
| 風速(アナログ) | 高速ポーリング | 50-100ms |
| 煙・扉(デジタル) | IRQ割り込み | < 1ms |

### Step 2: ハンドラ実装（MicroPython骨格）

```python
from machine import Pin
import time

class EmergencyHandler:
    def __init__(self, sensor_pin, actuator_pin, debounce_ms=50):
        self.sensor = Pin(sensor_pin, Pin.IN, Pin.PULL_UP)
        self.actuator = Pin(actuator_pin, Pin.OUT, value=0)
        self.blocked = False
        self._last = 0
        self.sensor.irq(trigger=Pin.IRQ_BOTH, handler=self._handler)

    def _handler(self, pin):
        now = time.ticks_ms()
        if time.ticks_diff(now, self._last) < 50:
            return
        self._last = now
        detected = not pin.value()
        if detected:
            self.actuator.off()
            self.blocked = True
```

### Step 3: 統合

- 複数センサーは `EmergencyManager` で一元管理（降雨+風速の組合せ等）
- アナログ(風速)は `ADC` + 別スレッドポーリングで対応
- RPi(Python3)の場合は `RPi.GPIO` + `add_event_detect` に置換

### Step 4: テスト

- IRQ: ピンをGND短絡→アクチュエータOFF確認
- ポーリング: ADCに閾値超の電圧印加→ロック確認
- `is_safe("irrigation")` で灌水許可判定をテスト

## Notes

- UECSとは独立した別系統として動作させる（安全系統の分離原則）
- デバウンスは50ms推奨（チャタリング防止）
- 関連: pico-gpio-relay, uecs-ccm-sender, sqlite-agri-analytics
