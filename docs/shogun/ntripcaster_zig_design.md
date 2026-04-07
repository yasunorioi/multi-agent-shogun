# ntripcaster Zigリライト設計書 — Phase 1: 原典読解＋設計

> **軍師分析書** | 2026-03-28 | cmd_463 / subtask_1022 | project: shogun

---

## §1 原典Cソース全機能リスト

### 1a. ソース構成概要

BKG製 ntripcaster 0.1.5（2003年、GPL v2）。Icecast 1.3.12ベースの改造。
10,464行(C)、14ソースファイル、1設定ファイル。

| ファイル | 行数 | 機能 |
|---------|------|------|
| **main.c** | 613 | エントリポイント、メインループ、シグナル処理、リスナー設定 |
| **source.c** | 800 | NTRIP Server(ソース)受信、RTCM3リレーエンジン |
| **client.c** | 849 | NTRIP Client接続、認証、Sourcetable配信、マウント管理 |
| **connection.c** | 612 | 接続ハンドラ、コネクションプール、DNS解決 |
| **sock.c** | 1,080 | ソケット操作全般(listen/accept/read/write/connect) |
| **threads.c** | 937 | POSIX threads抽象化、mutex管理、スレッドプール |
| **utility.c** | 1,299 | パスワード照合、confパース、リクエストビルダー、切断処理 |
| **ntrip_string.c** | 724 | 文字列操作、base64デコード、ヘッダー変数管理 |
| **timer.c** | 399 | カレンダースレッド、統計出力、タイムアウト管理 |
| **log.c** | 427 | ログファイル操作、デバッグ出力 |
| **avl.c** | 1,158 | AVLツリー実装（汎用コンテナ。ソース/クライアント/スレッド管理に使用） |
| **ntripcaster.h** | 345 | 全構造体定義、定数、サーバー情報グローバル |
| **definitions.h** | 78 | POSIX/GNU拡張マクロ定義 |
| 他ヘッダ | 計620 | 各モジュールのプロトタイプ宣言 |

### 1b. 機能別詳細

#### (1) NTRIP Server受信 — source.c

**何をやっているか**:
- `source_login()`: SOURCE コマンドをパースし、パスワード検証→マウントポイント登録→`source_func()`起動
- `source_func()`: ソーススレッドのメインループ。`add_chunk()` でRTCMデータを受信し、接続中の全クライアントに `source_write_to_client()` で配信
- `add_chunk()`: `recv()` でソースからバイナリデータを読み取り、リングバッファ（`chunk_t[64]`）に格納。75%充填 or タイムアウトで次チャンクへ
- リングバッファ設計: `CHUNKLEN=64` スロット、各 `SOURCE_BUFFSIZE=1000` バイト。`cid` が巡回インデックス

**なぜそうなっているか**:
- Icecast由来の「音声ストリーミング」パターン。RTCMバイナリも音声と同様に透過転送するため同じアーキテクチャが流用できた
- リングバッファは遅延クライアントの自動切断機構を兼ねる（`CHUNKLEN-1` エラーでキック）
- Source-Agent ヘッダーに "ntrip" が含まれない接続を拒否（NTRIP以外のソースを排除）

#### (2) NTRIP Client配信 — client.c

**何をやっているか**:
- `client_login()`: GETリクエストをパース→ヘッダー変数抽出→認証→マウント探索→コネクションプールに投入→`greet_client()`で "ICY 200 OK" 送信
- `send_sourcetable()`: "SOURCETABLE 200 OK" + Content-Type/Content-Length + sourcetable.dat内容 + "ENDSOURCETABLE"
- `greet_client()`: "ICY 200 OK" を返し、ソケットを非ブロッキングに設定、virgin=1 でデータ配信開始準備
- 認証フロー: `con_get_user()` → Authorization ヘッダーから Base64 デコード → user:pass 分離 → `authenticate_user_request()` でAVLツリー検索

**なぜそうなっているか**:
- NTRIP v1はICYプロトコル（SHOUTcast互換）。"ICY 200 OK" は意図的な非HTTP応答
- Sourcetableは `/` へのGETリクエストまたはマウント不一致時に返却される（フォールバック動作）
- User-Agentに "ntrip" を要求する検証あり（NTRIP v1仕様準拠）

#### (3) 接続管理 — connection.c

**何をやっているか**:
- `handle_connection()`: 新規接続スレッド。ヘッダー読み取り→ "GET" ならclient_login、"SOURCE" ならsource_login、それ以外は400エラー
- `get_connection()`: `select()` でリッスンソケット（最大5ポート）を多重化し、`accept()` で接続受理
- コネクションプール: `pool_add()` / `pool_get_my_clients()` — クライアントをプールに投入し、対応ソースが定期的に取り出す（producer-consumer）
- DNS解決: Linux/Solaris/標準の3系統の `gethostbyname_r` 対応（2003年のクロスプラットフォーム苦労）

**なぜそうなっているか**:
- 1接続1スレッドモデル（Icecast由来）。2003年時点のCサーバーでは標準的
- select()ベースの多重化はMAXLISTEN=5ポートに限定（epoll/io_uringは未使用）
- コネクションプールはソース→クライアントの非同期接続確立を仲介

#### (4) ソケット管理 — sock.c (1,080行)

**何をやっているか**:
- `sock_get_server_socket()`: socket→SO_REUSEADDR→bind→listen
- `sock_set_blocking()`: fcntl(F_SETFL, O_NONBLOCK) で非ブロッキング切替
- `sock_write_bytes()`: send()ループ（部分送信対応）
- `sock_read_lines()` / `sock_read_lines_np()`: 1バイトずつrecv()してHTTPヘッダー読み取り（\n\nで終了検出）
- `sock_write_line()`: printf形式でCRLF付き行送信
- `sock_connect_wto()`: タイムアウト付き非ブロッキングconnect（select待ち）

**なぜそうなっているか**:
- 1バイトrecvはHTTPヘッダー終端検出の素朴な実装。2003年のCサーバーでは一般的
- send()の部分送信ループは正しい実装（TCP保証外の動作対策）

#### (5) スレッド管理 — threads.c (937行)

**何をやっているか**:
- `thread_create_c()`: pthread_create()のラッパー。10回リトライ、detach済みスレッド生成
- AVLツリーでスレッド一覧管理（`info.threads`）
- mutex抽象化: `thread_create_mutex()` / `thread_mutex_lock()` / `thread_mutex_unlock()`
- メモリデバッグ: `nmalloc()` / `nfree()` ラッパー（DEBUG_MEMORY時にリーク追跡）
- `thread_wait_for_solitude()`: シャットダウン時に全スレッド終了を待機

**なぜそうなっているか**:
- Icecast由来の「自前スレッドプール」。Win32/POSIX抽象化レイヤー
- mutexの6重ロック設計（source_mutex, misc_mutex, mount_mutex, hostname_mutex, double_mutex, thread_mutex）は2003年の防衛的プログラミング

#### (6) 設定ファイル解析 — utility.c + main.c

**何をやっているか**:
- `parse_default_config_file()` → `setup_config_file_settings()`: ntripcaster.confをキーバリュー形式でパース
- 設定項目: port, max_clients, max_sources, encoder_password, server_name, logdir, logfile, location, rp_email, server_url
- マウント認証: `/<MOUNT>:user1:pass1,user2:pass2,...` 形式で設定ファイル末尾に記載
- SIGHUP で設定リロード（`sig_hup()` → `parse_default_config_file()` + `open_log_files()`）

**なぜそうなっているか**:
- Icecast由来の独自フォーマット。INI/TOML/YAMLではない平文キーバリュー
- 認証情報が同一ファイルに混在（セキュリティ観点では改善余地あり。ただし殿の方針「認証強化不要」）

#### (7) ログ出力 — log.c (427行)

**何をやっているか**:
- `write_log()`: printf形式でログファイル+コンソール出力
- `xa_debug()`: デバッグレベル付きログ（info.logfiledebuglevel, info.consoledebuglevel）
- `open_log_files()`: ログファイルオープン/リオープン（SIGHUP対応）

#### (8) タイマー — timer.c (399行)

**何をやっているか**:
- `startup_timer_thread()`: 別スレッドで定期実行
- `update_daily_statistics()` / `update_hourly_statistics()`: 統計情報リセット
- `print_statistics()`: 接続数・バイト数を定期ログ出力
- ソースタイムアウト: `pending_source_signoff()` — ソースが切断後、client_timeout秒待機して再接続を待つ

#### (9) AVLツリー — avl.c (1,158行)

汎用AVL平衡二分探索木。ソース一覧、クライアント一覧、スレッド一覧、マウント一覧、ユーザー一覧の全てに使用。
Zigリライトでは `std.Treap` or `std.ArrayHashMap` に置換可能。

### 1c. グローバルデータ構造

```c
server_info_t info;  // 全サーバー状態を保持するモノリシック構造体
// 主要フィールド:
//   .port[5], .listen_sock[5]      — 最大5ポート
//   .sources (AVL)                  — 接続中ソース一覧
//   .threads (AVL)                  — 全スレッド一覧
//   .num_clients, .max_clients     — クライアント管理
//   .num_sources, .max_sources     — ソース管理
//   .encoder_pass                   — ソース認証パスワード
//   .client_pass                    — クライアント認証パスワード
//   .source_mutex, .misc_mutex ... — 6個のmutex
//   .hourly_stats, .daily_stats   — 統計情報
```

### 1d. コード品質評価（リライトの動機）

| 問題 | 詳細 | Zig設計での解決 |
|------|------|----------------|
| **グローバル状態** | `server_info_t info` が全状態を保持。テスト不可能 | 構造体をインスタンス化し、依存性注入 |
| **mutex乱立** | 6個のmutex、ロック順序がコメントのみで管理 | Zigのcomptime強制+型レベル排他制御 |
| **1接続1スレッド** | 100クライアントで100スレッド。リソース浪費 | io_uring/epoll非同期ループ |
| **1バイトrecv** | ヘッダー読み取りが1バイトずつ | バッファードリーダー |
| **AVL everywhere** | 汎用AVLツリーが全コンテナ | HashMap/ArrayList選択 |
| **メモリ管理** | nmalloc/nfree手動管理、リーク追跡はDEBUG時のみ | Zigのアロケータ+ArenaAllocator |
| **errno依存** | スレッド安全でないerrno参照が多数 | Zigのerror union |
| **Win32対応** | #ifdef _WIN32 が全ファイルに散在 | Zigのクロスコンパイルで不要 |
| **2003年DNS** | gethostbyname_r 3系統分岐 | std.net.Address.resolveIp() |

---

## §2 NTRIPプロトコル仕様整理

### 2a. NTRIP v1（ICYプロトコル）— 現行実装

**Client → Caster (Sourcetable要求)**:
```
GET / HTTP/1.0\r\n
User-Agent: NTRIP ClientSoftware/Version\r\n
\r\n
```
応答:
```
SOURCETABLE 200 OK\r\n
Server: NTRIP NtripCaster/version\r\n
Content-Type: text/plain\r\n
Content-Length: {size}\r\n
\r\n
CAS;hostname;port;name;...
NET;network;operator;...
STR;mountpoint;city;format;...
ENDSOURCETABLE\r\n
```

**Client → Caster (データ要求)**:
```
GET /MOUNTPOINT HTTP/1.0\r\n
User-Agent: NTRIP ClientSoftware/Version\r\n
Authorization: Basic {base64(user:pass)}\r\n
\r\n
```
応答:
```
ICY 200 OK\r\n
\r\n
{RTCM3バイナリストリーム（無限長）}
```

**Source → Caster (データ送信)**:
```
SOURCE {password} /{MOUNTPOINT}\r\n
Source-Agent: NTRIP SourceSoftware/Version\r\n
\r\n
```
応答:
```
OK\r\n
{RTCM3バイナリストリーム受信開始}
```

### 2b. NTRIP v2（HTTP/1.1準拠）— 未実装（将来対応）

**Client → Caster**:
```
GET /MOUNTPOINT HTTP/1.1\r\n
Host: caster.example.com:2101\r\n
Ntrip-Version: Ntrip/2.0\r\n
User-Agent: NTRIP ClientSoftware/Version\r\n
Authorization: Basic {base64(user:pass)}\r\n
\r\n
```
応答:
```
HTTP/1.1 200 OK\r\n
Ntrip-Version: Ntrip/2.0\r\n
Transfer-Encoding: chunked\r\n
\r\n
{chunk-size}\r\n
{RTCM3データ}\r\n
...
```

**Source → Caster (v2: POST化)**:
```
POST /MOUNTPOINT HTTP/1.1\r\n
Host: caster.example.com:2101\r\n
Ntrip-Version: Ntrip/2.0\r\n
Authorization: Basic {base64(user:pass)}\r\n
Transfer-Encoding: chunked\r\n
\r\n
```

### 2c. v1 vs v2 差分表

| 項目 | NTRIP v1 | NTRIP v2 |
|------|----------|----------|
| クライアント応答 | `ICY 200 OK` | `HTTP/1.1 200 OK` |
| ソース送信 | `SOURCE pass /mount` | `POST /mount HTTP/1.1` |
| Sourcetable応答 | `SOURCETABLE 200 OK` | `HTTP/1.1 200 OK` |
| Transfer-Encoding | なし（無限ストリーム） | chunked |
| Hostヘッダー | 不要 | 必須 |
| Ntrip-Versionヘッダー | なし | `Ntrip/2.0` |
| RTSP対応 | なし | あり |
| RTKLIBとの互換性 | **あり** | **なし** |

### 2d. Sourcetableレコード形式

```
STR;mountpoint;city;format;format-details;carrier;nav-system;network;country;lat;lon;nmea;solution;generator;compression;auth;fee;bitrate;misc
CAS;host;port;identifier;operator;nmea;country;lat;lon;fallback_host
NET;identifier;operator;authentication;fee;web-net;web-str;web-reg;misc
```

### 2e. RTCM3バイナリリレーの仕組み

**パース不要、透過転送**。キャスターはRTCM3メッセージの内容を一切解釈しない。
バイナリデータをソースからrecv()し、そのまま全クライアントにsend()する。

唯一の例外: `find_frame_ofs()` — RTCM3フレーム同期（0xD3先頭バイト検出）で
新規クライアントの開始位置を調整する。ただしntripcaster実装ではMP3フレーム同期
（0xFF 0xF0）のIcecastコードがそのまま残っており、RTCM3としては不正確。

### 2f. BKG仕様書と実装の差異

1. **User-Agent検証**: 仕様では推奨、実装では`strncasecmp(agent, "ntrip", 5)`で**強制**
2. **NTRIP v2未対応**: 実装はv1のみ。chunked transfer encodingは未実装
3. **RTCM3フレーム同期**: 実装はMP3同期（0xFF 0xF0）を流用。RTCM3は0xD3が正しい
4. **パスワード暗号化**: USE_CRYPT有効時はcrypt()使用だが、デフォルトは平文比較

---

## §3 Zig実装設計 — モジュール構成

### 3a. ディレクトリ構成

```
ntripcaster/
├── src/
│   ├── main.zig              # エントリポイント、設定読み込み、サーバー起動
│   ├── server.zig            # TCPリスナー、接続振り分け
│   ├── ntrip/
│   │   ├── protocol.zig      # NTRIP v1/v2プロトコルパーサー
│   │   ├── source.zig        # ソース接続ハンドラ
│   │   ├── client.zig        # クライアント接続ハンドラ
│   │   └── sourcetable.zig   # Sourcetable管理・配信
│   ├── relay/
│   │   └── engine.zig        # RTCM3リレーエンジン（リングバッファ）
│   ├── auth/
│   │   └── basic.zig         # Basic認証（Base64デコード+ユーザー照合）
│   ├── config/
│   │   └── parser.zig        # ntripcaster.conf パーサー（後方互換）
│   └── log.zig               # ログ出力
├── build.zig                  # ビルド定義（クロスコンパイル対応）
├── conf/
│   └── ntripcaster.conf       # 設定ファイル（現行形式互換）
├── legacy/                    # 原典Cソース保存
│   └── src/
└── tests/
    ├── test_protocol.zig      # プロトコルパーサーテスト
    ├── test_relay.zig         # リレーエンジンテスト
    ├── test_auth.zig          # 認証テスト
    └── test_config.zig        # 設定パーサーテスト
```

### 3b. モジュール依存関係

```
main.zig
  ├── config/parser.zig       ← 設定読み込み
  ├── server.zig              ← TCPリスナー起動
  │   ├── ntrip/protocol.zig  ← ヘッダーパース
  │   ├── ntrip/source.zig    ← ソース処理
  │   │   └── relay/engine.zig ← リングバッファ
  │   ├── ntrip/client.zig    ← クライアント処理
  │   │   ├── auth/basic.zig  ← 認証
  │   │   └── ntrip/sourcetable.zig ← Sourcetable配信
  │   └── log.zig             ← ログ出力
  └── log.zig
```

**依存方向**: 上位 → 下位のみ。循環依存なし。

### 3c. Cソースとの対応表

| Cソース | Zigモジュール | 変更理由 |
|---------|-------------|---------|
| main.c (613行) | main.zig + server.zig | サーバーループを分離 |
| source.c (800行) | ntrip/source.zig + relay/engine.zig | リレーエンジンを分離 |
| client.c (849行) | ntrip/client.zig + auth/basic.zig + ntrip/sourcetable.zig | 認証・Sourcetableを分離 |
| connection.c (612行) | server.zig | プール+DNS→サーバーに統合 |
| sock.c (1,080行) | std.net使用（不要） | Zig標準ライブラリで代替 |
| threads.c (937行) | std.Thread使用（不要） | Zig標準ライブラリで代替 |
| utility.c (1,299行) | 各モジュールに分散 | monolithicユーティリティを分解 |
| ntrip_string.c (724行) | 各モジュール + std | Zig標準の文字列処理で代替 |
| timer.c (399行) | server.zig内のタイマー | 別スレッド→イベントループ内で処理 |
| log.c (427行) | log.zig | ほぼ1:1対応 |
| avl.c (1,158行) | std.HashMap / std.ArrayList | Zig標準コンテナで代替 |
| ntripcaster.h (345行) | 各モジュールの型定義に分散 | グローバル構造体を解体 |

**推定行数**: Zig全体で約2,000-2,500行（C 10,464行の約25%。Win32対応/AVL/autotools削除分）

---

## §4 Zig実装設計 — アーキテクチャ

### 4a. I/Oモデル

**推奨: std.net + スレッドプール（Phase 2）。将来的にio_uring移行（Phase 3以降）。**

```zig
// Phase 2: std.netベースの同期I/O + スレッドプール
const server = try std.net.Address.parseIp4("0.0.0.0", config.port);
var listener = try server.listen(.{ .reuse_address = true });
defer listener.deinit();

// スレッドプールで接続処理
var pool = try std.Thread.Pool.init(.{ .n_jobs = config.max_clients });
defer pool.deinit();

while (true) {
    const conn = try listener.accept();
    try pool.spawn(handleConnection, .{conn, &state});
}
```

**io_uringを初手で使わない理由**:
1. Zig 0.14のstd.netは十分に安定。io_uringはLinux 5.1+限定
2. ntripcasterの同時接続数は現実的に10-50程度（RTK基準局ネットワーク）。スレッドプールで十分
3. 殿のRPi（aarch64 Linux 5.15+）はio_uring対応しているが、まず動くものを優先
4. 外部依存ゼロの方針に合致（zig-aio等は使わない）

### 4b. リングバッファ設計（Cからの改善）

```zig
pub const RingBuffer = struct {
    const CHUNK_SIZE: usize = 4096;  // C: 1000→4096に拡大
    const NUM_CHUNKS: usize = 64;

    chunks: [NUM_CHUNKS][CHUNK_SIZE]u8 = undefined,
    lengths: [NUM_CHUNKS]usize = [_]usize{0} ** NUM_CHUNKS,
    write_pos: usize = 0,
    // クライアント別読み取り位置はclient.zig側で管理

    pub fn writeChunk(self: *RingBuffer, data: []const u8) void {
        const pos = self.write_pos % NUM_CHUNKS;
        const len = @min(data.len, CHUNK_SIZE);
        @memcpy(self.chunks[pos][0..len], data[0..len]);
        self.lengths[pos] = len;
        self.write_pos +%= 1;
    }
};
```

**C実装からの改善点**:
- `CHUNK_SIZE` 1000→4096: RTCM3メッセージの最大長は4095バイト。1チャンクに1メッセージが収まる
- `clients_left` カウンタ廃止: クライアントが自分のread_posを管理する方式に変更（ロック削減）
- `find_frame_ofs()` 修正: 0xFF 0xF0（MP3）→ 0xD3（RTCM3フレームプリアンブル）

### 4c. 状態管理（グローバル排除）

```zig
pub const ServerState = struct {
    config: Config,
    sources: std.StringHashMap(*Source),     // マウント名→ソース
    source_lock: std.Thread.Mutex = .{},
    stats: Statistics = .{},
    allocator: std.mem.Allocator,
    log: Logger,

    pub fn init(allocator: std.mem.Allocator, config: Config) ServerState { ... }
    pub fn deinit(self: *ServerState) void { ... }
};
```

Cの `server_info_t info` グローバル変数 → `ServerState` 構造体をインスタンス化。
全関数に `*ServerState` を渡す。テスト時にモック状態を注入可能。

### 4d. 認証設計

```zig
pub const Authenticator = struct {
    mounts: std.StringHashMap(MountAuth),  // マウント名→認証設定
    encoder_pass: []const u8,

    pub fn authenticateClient(self: *const Authenticator, mount: []const u8, user: []const u8, pass: []const u8) bool { ... }
    pub fn authenticateSource(self: *const Authenticator, password: []const u8) bool { ... }
};
```

殿の方針「認証強化不要」に準拠。Basic認証のみ。現行confファイルの認証行をそのままパース。

### 4e. NTRIP v1/v2 プロトコルパーサー

```zig
pub const NtripRequest = union(enum) {
    source_login: SourceLogin,    // "SOURCE pass /mount"
    client_get: ClientGet,        // "GET /mount HTTP/1.x"
    sourcetable_get: void,        // "GET / HTTP/1.x"
    invalid: []const u8,
};

pub fn parseRequest(header: []const u8) NtripRequest {
    if (std.mem.startsWith(u8, header, "SOURCE ")) return .{ .source_login = parseSourceLogin(header) };
    if (std.mem.startsWith(u8, header, "GET ")) return parseGet(header);
    return .{ .invalid = header };
}
```

**v1/v2判定**: `Ntrip-Version: Ntrip/2.0` ヘッダーの有無で分岐。
Phase 2ではv1のみ実装。v2（chunked transfer）はPhase 3以降。

---

## §5 ビルド・デプロイ設計

### 5a. build.zig

```zig
const std = @import("std");

pub fn build(b: *std.Build) void {
    const target = b.standardTargetOptions(.{});
    const optimize = b.standardOptimizeOption(.{});

    const exe = b.addExecutable(.{
        .name = "ntripcaster",
        .root_source_file = b.path("src/main.zig"),
        .target = target,
        .optimize = optimize,
    });
    b.installArtifact(exe);

    // テスト
    const tests = b.addTest(.{
        .root_source_file = b.path("tests/test_all.zig"),
        .target = target,
        .optimize = optimize,
    });
    const run_tests = b.addRunArtifact(tests);
    const test_step = b.step("test", "Run unit tests");
    test_step.dependOn(&run_tests.step);
}
```

### 5b. クロスコンパイルターゲット

| ターゲット | 用途 | コマンド |
|-----------|------|---------|
| x86_64-linux | MBP/VPS | `zig build` |
| aarch64-linux | RPi 4/5 | `zig build -Dtarget=aarch64-linux` |
| arm-linux-gnueabihf | RPi 3/Zero 2W | `zig build -Dtarget=arm-linux-gnueabihf` |
| x86_64-macos | MBP macOS | `zig build -Dtarget=x86_64-macos` |
| aarch64-macos | MBP M-series | `zig build -Dtarget=aarch64-macos` |

**外部依存ゼロ**: Zig std libのみ。libwrap、autotools、pthread明示リンク全て不要。

### 5c. systemd連携

cmd_461で作成済みの `ntripcaster.service` をそのまま流用可能:
- ExecStart パスをZigバイナリに変更するだけ
- WorkingDirectory、User、RestartOnFailure は変更不要
- confファイルパスも後方互換で同一

### 5d. 移行計画

```
Phase 1 (本文書): 原典読解 + 設計書作成 ← 完了
Phase 2: Zig実装（v1プロトコル、最小構成）
  → src/main.zig〜relay/engine.zig の全モジュール
  → テスト: RTKLIB str2str との相互運用テスト
Phase 3: v2対応（chunked transfer）+ RTCM3フレーム同期修正
Phase 4: io_uring非同期化（Linux限定、オプション）
Phase 5: パッケージング（GitHub Release、deb/rpm）
```

---

## §6 トレードオフ比較

| 案 | 内容 | 利点 | 欠点 | 推奨 |
|----|------|------|------|------|
| **A: Zig std.net + ThreadPool** | 同期I/O + スレッドプール | 単純、外部依存ゼロ、デバッグ容易 | 大規模時にスレッド浪費 | ★★★ |
| **B: Zig io_uring直接** | Linux io_uring非同期 | 最高性能 | Linux限定、複雑 | ★（Phase 4以降） |
| **C: zig-aio外部依存** | io_uring抽象化ライブラリ | クロスプラットフォーム非同期 | 外部依存、殿方針違反 | ★ |
| **D: C改修のみ** | 既存Cコードにパッチ | 最小労力 | 根本問題(グローバル状態、Win32)未解決 | ★ |

---

## §7 リスク・見落とし分析

1. **RTKLIB互換性**: RTKLIBはNTRIP v1のみ対応。v1互換を最優先し、v2は後回し
   - **検証方法**: str2str -in ntrip://:BUCU0@localhost:2101 でストリーム受信テスト

2. **RTCM3フレーム同期の影響**: 現行実装のMP3同期(0xFF 0xF0)は「たまたま動く」状態。修正すると既存クライアントの挙動が変わる可能性
   - **対策**: Phase 2では現行動作を再現、Phase 3で正しいRTCM3同期に移行

3. **設定ファイル互換性**: 現行confファイルを100%パースできること
   - **検証方法**: 既存ntripcaster.confをZig版でパースし、C版と同一設定になることを確認

4. **マルチポートリスナー**: MAXLISTEN=5の制限。現行運用では1ポート(2101)のみ使用？
   - **対策**: 設計では配列で対応。実運用確認は殿に要確認

5. **pending_source_signoff**: ソース切断時のclient_timeoutロジックが複雑。挙動の正確な再現が必要
   - **対策**: テストケースで検証。C版との並行稼働テスト期間を設ける

---

## §8 North Star 整合確認

| 観点 | 判定 |
|------|------|
| マクガイバー精神（最小コスト） | ✅ Zig std libのみ。外部依存ゼロ |
| 月額ゼロ | ✅ OSS、ビルドツールチェーンのみ |
| NTRIP互換性最優先 | ✅ v1完全互換→v2段階的対応 |
| 設定ファイル後方互換 | ✅ 現行conf形式をそのままパース |
| クロスコンパイル | ✅ RPi/VPS/MBP全てZig build一発 |
| RPi放置運用 | ✅ systemd流用、シングルバイナリデプロイ |
| 原典保存 | ✅ /legacy/に保存、削除しない |

---

## §9 推奨アクション

1. **Phase 2を3 subtaskに分割して即着手可能** — 各モジュールは独立実装可能
2. **最初のマイルストーン**: `zig build && ./ntripcaster --test` でSourcetable応答確認
3. **RTKLIB str2strとの相互運用テストをPhase 2完了条件に含める**
4. **RTCM3フレーム同期の修正はPhase 3に延期**（互換性リスク回避）
5. **マルチポートリスナーの実運用要否を殿に確認**

---

*古い城を壊す前に、まず全ての部屋の間取りを知れ。——リライトの鉄則。*

Sources:
- [NTRIP Rev1 vs Rev2 - SNIP](https://www.use-snip.com/kb/knowledge-base/ntrip-rev1-versus-rev2-formats/)
- [BKG NTRIP Official](https://igs.bkg.bund.de/ntrip/)
- [NTRIP v1.0 Specification (ESA)](https://gssc.esa.int/wp-content/uploads/2018/07/NtripDocumentation.pdf)
- [Zig TCP Server Guide](https://www.openmymind.net/TCP-Server-In-Zig-Part-1-Single-Threaded/)
- [zig-aio io_uring library](https://github.com/Clouded/zig-aio)
- [Zig std.net Sockets](https://ziggit.dev/t/sockets-with-std-net-in-zig-0-13-0/8437)
