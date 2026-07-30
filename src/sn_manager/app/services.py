"""序列号应用服务：生成、筛选、状态与主数据编排。"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date
from typing import Any

from sn_manager.core.status import Status
from sn_manager.db import master_data as md
from sn_manager.db import serials as ser


@dataclass(frozen=True)
class MasterSnapshot:
    """主数据对话框提交的完整快照。"""

    product_models: list[str]
    hardware_batches: list[str]
    factories: list[tuple[str, str]]
    markets: list[tuple[str, str]]


class SnService:
    """编排 db 层操作的序列号服务。"""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def generate(
        self,
        *,
        product_model: str,
        hw_batch: str,
        factory: str,
        market: str,
        prod_date: date,
        count: int,
        ensure_master: bool = True,
    ) -> list[dict[str, Any]]:
        if ensure_master:
            self._ensure_master(product_model, hw_batch, factory, market)

        sns = ser.allocate_and_insert(
            self.conn,
            product_model=product_model,
            hw_batch=hw_batch,
            factory=factory,
            market=market,
            prod_date=prod_date,
            count=count,
        )
        return [ser.filter_serials(self.conn, sn=sn)[0] for sn in sns]

    def filter(self, **criteria: Any) -> list[dict[str, Any]]:
        return ser.filter_serials(self.conn, **criteria)

    def set_status(self, sns: list[str], status: Status) -> None:
        ser.update_statuses(self.conn, sns, status)

    def replace_master_data(self, snapshot: MasterSnapshot) -> None:
        self._sync_codes(
            "product_models",
            {row["code"] for row in md.list_product_models(self.conn)},
            {code.upper() for code in snapshot.product_models},
            md.delete_product_model,
            lambda code: md.upsert_product(self.conn, code),
        )
        self._sync_codes(
            "hardware_batches",
            {row["code"] for row in md.list_hardware_batches(self.conn)},
            {code.upper() for code in snapshot.hardware_batches},
            md.delete_hardware_batch,
            lambda code: md.upsert_hardware_batch(self.conn, code),
        )
        self._sync_named(
            md.list_factories,
            {(code, name) for code, name in snapshot.factories},
            md.delete_factory,
            lambda code, name: md.upsert_factory(self.conn, code, name),
        )
        self._sync_named(
            md.list_markets,
            {(code, name) for code, name in snapshot.markets},
            md.delete_market,
            lambda code, name: md.upsert_market(self.conn, code, name),
        )

    def _ensure_master(
        self,
        product_model: str,
        hw_batch: str,
        factory: str,
        market: str,
    ) -> None:
        model = product_model.strip().upper()
        batch = hw_batch.strip().upper()
        fac = factory.strip().upper()
        mkt = market.strip().upper()
        self.conn.execute(
            "INSERT OR IGNORE INTO product_models (code) VALUES (?)",
            (model,),
        )
        self.conn.execute(
            "INSERT OR IGNORE INTO hardware_batches (code) VALUES (?)",
            (batch,),
        )
        self.conn.execute(
            "INSERT OR IGNORE INTO factories (code, name) VALUES (?, ?)",
            (fac, fac),
        )
        self.conn.execute(
            "INSERT OR IGNORE INTO markets (code, name) VALUES (?, ?)",
            (mkt, mkt),
        )
        self.conn.commit()

    def _sync_codes(
        self,
        _table: str,
        existing: set[str],
        desired: set[str],
        delete_fn: Any,
        upsert_fn: Any,
    ) -> None:
        for code in existing - desired:
            delete_fn(self.conn, code)
        for code in sorted(desired):
            upsert_fn(code)

    def _sync_named(
        self,
        list_fn: Any,
        desired: set[tuple[str, str]],
        delete_fn: Any,
        upsert_fn: Any,
    ) -> None:
        existing = {row["code"] for row in list_fn(self.conn)}
        desired_codes = {code for code, _ in desired}
        for code in existing - desired_codes:
            delete_fn(self.conn, code)
        for code, name in sorted(desired):
            upsert_fn(code, name)
