"""EC ログ分類の合成データセット生成。

実ログが用意できるまでの評価用。テンプレート × ランダムなスロット値で各ラベル同数を生成する。
seed 固定なので同じ引数なら同じファイルになる（生成物は data/samples/ にコミットする）。

サービス名だけで当たらないよう、ラベルと無関係なサービスが出すログ
（payment-svc の正常ログ、api-gw が出す決済エラーなど）も混ぜている。

    uv run hellow-jev-synth                      # 既定: 各ラベル 50 件
    uv run hellow-jev-synth --per-label 100 --out data/processed/synth_700.jsonl
"""

from __future__ import annotations

import argparse
import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

from hellow_jev.task import REPO_ROOT, load_task

DEFAULT_OUT = REPO_ROOT / "data/samples/ec_logs_synth.jsonl"
DEFAULT_SEED = 20260927
DEFAULT_PER_LABEL = 50

# (level, service, message) を返す関数。r はスロット値の乱数源
Template = Callable[[random.Random], tuple[str, str, str]]


def _order(r: random.Random) -> str:
    return f"ORD-{r.randint(10000, 99999)}"


def _user(r: random.Random) -> str:
    return f"u_{r.randint(1000, 99999)}"


def _sku(r: random.Random) -> str:
    return f"SKU-{r.randint(1000, 9999)}"


def _ip(r: random.Random) -> str:
    # ドキュメント用アドレス帯（RFC 5737）
    block = r.choice(["192.0.2", "198.51.100", "203.0.113"])
    return f"{block}.{r.randint(1, 254)}"


def _path(r: random.Random) -> str:
    return r.choice(["/api/cart", "/api/checkout", "/api/orders", "/api/products", "/api/search", "/api/account"])


def _ms(r: random.Random, lo: int, hi: int) -> int:
    return r.randint(lo, hi) // 10 * 10


TEMPLATES: dict[str, list[Template]] = {
    "payment": [
        lambda r: ("ERROR", "payment-svc", f"charge failed: {r.choice(['card_declined', 'insufficient_funds', 'expired_card', 'do_not_honor'])} order={_order(r)} amount={r.randint(500, 50000)}"),
        lambda r: ("WARN", "payment-svc", f"3DS authentication failed for order={_order(r)} reason={r.choice(['challenge_abandoned', 'authentication_rejected'])}"),
        lambda r: ("ERROR", "checkout-svc", f"refund request rejected by provider order={_order(r)} code=R{r.randint(10, 99)}"),
        lambda r: ("ERROR", "api-gw", f"POST /api/payments returned 402 Payment Required order={_order(r)}"),
        lambda r: ("WARN", "billing-svc", f"invoice amount mismatch order={_order(r)} expected={r.randint(1000, 9000)} captured={r.randint(1000, 9000)}"),
        lambda r: ("ERROR", "payment-svc", f"duplicate capture detected for order={_order(r)} txn=TX{r.randint(100000, 999999)}"),
        lambda r: ("ERROR", "subscription-svc", f"recurring charge failed for user={_user(r)} plan={r.choice(['prime', 'plus', 'family'])} retry={r.randint(1, 3)}/3"),
        lambda r: ("WARN", "payment-svc", f"chargeback received order={_order(r)} reason_code={r.choice(['4837', '4853', '10.4', '13.1'])}"),
        lambda r: ("ERROR", "checkout-svc", f"coupon applied twice, negative total {-r.randint(1, 900)} for order={_order(r)}"),
        lambda r: ("ERROR", "payment-svc", f"settlement batch {r.randint(100, 999)} failed: {r.randint(2, 40)} transactions not reconciled"),
    ],
    "auth": [
        lambda r: ("WARN", "auth-svc", f"invalid password attempt user={_user(r)} count={r.randint(1, 4)}"),
        lambda r: ("ERROR", "api-gw", f"401 Unauthorized: token expired path={_path(r)}"),
        lambda r: ("WARN", "auth-svc", f"refresh token revoked user={_user(r)} client={r.choice(['ios', 'android', 'web'])}"),
        lambda r: ("ERROR", "auth-svc", f"OAuth callback failed provider={r.choice(['google', 'apple', 'line'])}: invalid_grant"),
        lambda r: ("WARN", "web-frontend", f"session cookie missing, redirecting to /login user={_user(r)}"),
        lambda r: ("ERROR", "auth-svc", f"MFA code verification failed user={_user(r)} method={r.choice(['sms', 'totp', 'email'])}"),
        lambda r: ("WARN", "cart-svc", f"request rejected: session expired session=sess_{r.randint(100000, 999999)}"),
        lambda r: ("ERROR", "auth-svc", f"JWT signature verification failed kid=key-{r.randint(1, 9)}"),
        lambda r: ("WARN", "auth-svc", f"account locked after failed logins user={_user(r)}"),
        lambda r: ("ERROR", "account-svc", f"password reset link expired user={_user(r)}"),
    ],
    "inventory": [
        lambda r: ("ERROR", "inventory-svc", f"reserve failed: out of stock sku={_sku(r)} requested={r.randint(1, 5)}"),
        lambda r: ("WARN", "inventory-svc", f"stock sync lag {r.randint(120, 1800)}s from warehouse=WH-{r.randint(1, 9)}"),
        lambda r: ("ERROR", "checkout-svc", f"cannot place order={_order(r)}: item {_sku(r)} no longer available"),
        lambda r: ("WARN", "inventory-svc", f"negative stock detected sku={_sku(r)} qty={-r.randint(1, 20)}"),
        lambda r: ("ERROR", "catalog-svc", f"SKU mapping not found for vendor code V{r.randint(10000, 99999)}"),
        lambda r: ("WARN", "inventory-svc", f"reservation for order={_order(r)} expired before payment, releasing {r.randint(1, 4)} units"),
        lambda r: ("ERROR", "wms-connector", f"stock feed import failed: {r.randint(3, 200)} rows rejected, unknown sku"),
        lambda r: ("WARN", "inventory-svc", f"oversell: sku={_sku(r)} sold={r.randint(11, 20)} available={r.randint(0, 10)}"),
        lambda r: ("WARN", "search-svc", f"product {_sku(r)} shown as in stock but inventory reports 0"),
        lambda r: ("ERROR", "inventory-svc", f"stock adjustment conflict sku={_sku(r)} version mismatch"),
    ],
    "shipping": [
        lambda r: ("ERROR", "shipping-svc", f"carrier API returned {r.choice([500, 502, 503])} for shipment=SHP-{r.randint(1000, 9999)}"),
        lambda r: ("WARN", "shipping-svc", f"tracking number not found tracking=JP{r.randint(100000000, 999999999)}"),
        lambda r: ("ERROR", "fulfillment-svc", f"pick list generation failed for order={_order(r)}: warehouse unassigned"),
        lambda r: ("WARN", "shipping-svc", f"address validation failed order={_order(r)} postal_code={r.randint(100, 999)}-{r.randint(1000, 9999)}"),
        lambda r: ("ERROR", "shipping-svc", f"label creation failed carrier={r.choice(['yamato', 'sagawa', 'japanpost'])}: invalid package dimensions"),
        lambda r: ("WARN", "fulfillment-svc", f"order={_order(r)} not shipped within SLA ({r.randint(49, 96)}h since payment)"),
        lambda r: ("WARN", "notification-svc", f"delivery status webhook rejected: unknown shipment SHP-{r.randint(1000, 9999)}"),
        lambda r: ("ERROR", "shipping-svc", f"delivery date calculation failed: no carrier serves region={r.choice(['okinawa', 'hokkaido', 'remote-island'])}"),
        lambda r: ("WARN", "shipping-svc", f"package returned to sender shipment=SHP-{r.randint(1000, 9999)} reason=address_unknown"),
        lambda r: ("ERROR", "order-svc", f"shipping fee lookup failed for order={_order(r)}: rate table missing"),
    ],
    "performance": [
        lambda r: ("WARN", "api-gw", f"upstream timeout after {_ms(r, 10000, 60000)}ms path={_path(r)}"),
        lambda r: ("WARN", "search-svc", f"p99 latency {_ms(r, 1500, 9000)}ms exceeds SLO"),
        lambda r: ("ERROR", "cart-svc", f"OutOfMemoryError: Java heap space (heap={r.choice([2, 4, 8])}g)"),
        lambda r: ("WARN", "order-db", f"slow query {_ms(r, 3000, 30000)}ms: SELECT * FROM orders WHERE user_id = ?"),
        lambda r: ("WARN", "k8s", f"pod checkout-svc-{r.randint(1000, 9999)} CPU throttled {r.randint(60, 99)}%"),
        lambda r: ("ERROR", "db-pool", f"connection pool exhausted: {r.choice([50, 100, 200])}/{r.choice([50, 100, 200])} in use, wait timeout"),
        lambda r: ("WARN", "cache", f"redis latency spike {_ms(r, 200, 3000)}ms, hit ratio {r.randint(10, 60)}%"),
        lambda r: ("ERROR", "product-svc", f"request queue full, dropping requests (queue_size={r.choice([1000, 5000])})"),
        lambda r: ("WARN", "node-exporter", f"disk usage {r.randint(90, 99)}% on /var/lib/postgresql"),
        lambda r: ("WARN", "payment-svc", f"thread pool saturated active={r.randint(190, 200)}/200 queue={r.randint(50, 900)}"),
    ],
    "security": [
        lambda r: ("ALERT", "waf", f"blocked request: sql injection pattern in query param {r.choice(['q', 'id', 'sort'])}"),
        lambda r: ("WARN", "auth-svc", f"brute force suspected from {_ip(r)}, {r.randint(60, 500)} failures/min"),
        lambda r: ("ALERT", "waf", f"XSS payload detected in review body product={_sku(r)} src={_ip(r)}"),
        lambda r: ("WARN", "bot-detector", f"scraping suspected: {r.randint(2000, 20000)} product page requests/hour from {_ip(r)}"),
        lambda r: ("ALERT", "auth-svc", f"credential stuffing: {r.randint(100, 3000)} distinct accounts tried from {_ip(r)}"),
        lambda r: ("WARN", "checkout-svc", f"card testing suspected: {r.randint(20, 200)} small authorizations from {_ip(r)} in 5min"),
        lambda r: ("ALERT", "admin-panel", f"access to /admin from non-allowlisted ip {_ip(r)}"),
        lambda r: ("WARN", "api-gw", f"path traversal attempt path=/static/../../etc/passwd src={_ip(r)}"),
        lambda r: ("ALERT", "account-svc", f"user={_user(r)} email changed and password reset from new country within 2min"),
        lambda r: ("WARN", "bot-detector", f"inventory hoarding bot: {r.randint(50, 400)} carts created by {_ip(r)} for limited item {_sku(r)}"),
    ],
    "normal": [
        lambda r: ("INFO", "auth-svc", f"login success user={_user(r)}"),
        lambda r: ("INFO", "order-svc", f"order completed order={_order(r)}"),
        lambda r: ("INFO", "lb", f"healthcheck ok target=web-{r.randint(1, 9)}"),
        lambda r: ("INFO", "payment-svc", f"charge succeeded order={_order(r)} amount={r.randint(500, 50000)}"),
        lambda r: ("INFO", "inventory-svc", f"restock completed sku={_sku(r)} qty={r.randint(10, 500)}"),
        lambda r: ("INFO", "shipping-svc", f"shipment SHP-{r.randint(1000, 9999)} delivered"),
        lambda r: ("INFO", "api-gw", f"GET {_path(r)} 200 {_ms(r, 20, 180)}ms"),
        lambda r: ("INFO", "deploy", f"rollout checkout-svc v1.{r.randint(10, 60)}.{r.randint(0, 9)} completed"),
        lambda r: ("INFO", "auth-svc", f"token refreshed user={_user(r)}"),
        lambda r: ("INFO", "cron", f"nightly sales report generated rows={r.randint(1000, 90000)}"),
    ],
}


def generate(labels: list[str], per_label: int, seed: int) -> list[dict]:
    """各ラベル per_label 件を生成し、シャッフルした上で時刻・id を振る。"""
    if set(TEMPLATES) != set(labels):
        raise ValueError(f"templates and task labels differ: task={labels} templates={sorted(TEMPLATES)}")
    r = random.Random(seed)
    items: list[tuple[str, str, str, str]] = []
    for label in labels:
        templates = TEMPLATES[label]
        for i in range(per_label):
            # テンプレートを均等に使う（件数の偏りでラベル内の難易度がぶれないように）
            level, service, message = templates[i % len(templates)](r)
            items.append((label, level, service, message))
    r.shuffle(items)
    t = datetime(2026, 9, 1, 9, 0, tzinfo=timezone.utc)
    records = []
    for n, (label, level, service, message) in enumerate(items, 1):
        t += timedelta(seconds=r.randint(1, 90))
        ts = t.strftime("%Y-%m-%dT%H:%M:%SZ")
        # 一部は構造化ログ（JSON 1 行）にして表記の揺れを入れる
        if r.random() < 0.2:
            text = json.dumps({"ts": ts, "level": level, "service": service, "msg": message})
        else:
            text = f"{ts} {level} {service} {message}"
        records.append({"id": f"g{n:04d}", "text": text, "label": label})
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description="EC ログ分類の合成データセットを生成する")
    parser.add_argument("--task", default="log_classification")
    parser.add_argument("--per-label", type=int, default=DEFAULT_PER_LABEL)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    task = load_task(args.task)
    records = generate(task.label_names, args.per_label, args.seed)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    print(f"wrote {len(records)} records -> {args.out}")


if __name__ == "__main__":
    main()
