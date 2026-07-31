"""序列号应用服务：生成、筛选、状态与主数据编排。"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date
from typing import Any, Callable

from sn_manager.core.errors import ValidationError
from sn_manager.core.status import Status
from sn_manager.db import master_data as md
from sn_manager.db import serials as ser


@dataclass(frozen=True)
class MasterSnapshot:
    """主数据对话框提交的完整快照。"""

    product_models: list[tuple[str, str]]
    hardware_batches: list[tuple[str, str]]
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
    ) -> list[dict[str, Any]]:
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

    def apply_master_data(self, snapshot: MasterSnapshot) -> None:
        """主数据对话框确认时一次性同步四类主数据。"""
        self.replace_master_data(snapshot)

    def replace_master_data(self, snapshot: MasterSnapshot) -> None:
        validated = self._validate_snapshot(snapshot)
        try:
            self._sync_named(
                md.list_product_models,
                set(validated.product_models),
                md.delete_product_model,
                lambda code, name: md.upsert_product(
                    self.conn, code, name, commit=False
                ),
                commit=False,
            )
            self._sync_named(
                md.list_hardware_batches,
                set(validated.hardware_batches),
                md.delete_hardware_batch,
                lambda code, name: md.upsert_hardware_batch(
                    self.conn, code, name, commit=False
                ),
                commit=False,
            )
            self._sync_named(
                md.list_factories,
                set(validated.factories),
                md.delete_factory,
                lambda code, name: md.upsert_factory(
                    self.conn, code, name, commit=False
                ),
                commit=False,
            )
            self._sync_named(
                md.list_markets,
                set(validated.markets),
                md.delete_market,
                lambda code, name: md.upsert_market(
                    self.conn, code, name, commit=False
                ),
                commit=False,
            )
            self.conn.commit()
        except ValidationError:
            self.conn.rollback()
            raise

    def _validate_snapshot(self, snapshot: MasterSnapshot) -> MasterSnapshot:
        return MasterSnapshot(
            product_models=[
                (md.validate_product_code(code), md.validate_name(name))
                for code, name in snapshot.product_models
            ],
            hardware_batches=[
                (md.validate_hardware_batch_code(code), md.validate_name(name))
                for code, name in snapshot.hardware_batches
            ],
            factories=[
                (md.validate_factory_code(code), md.validate_name(name))
                for code, name in snapshot.factories
            ],
            markets=[
                (md.validate_market_code(code), md.validate_name(name))
                for code, name in snapshot.markets
            ],
        )

    def _sync_named(
        self,
        list_fn: Callable[[sqlite3.Connection], list[dict[str, Any]]],
        desired: set[tuple[str, str]],
        delete_fn: Callable[..., None],
        upsert_fn: Callable[[str, str], None],
        *,
        commit: bool = True,
    ) -> None:
        existing = {row["code"] for row in list_fn(self.conn)}
        desired_codes = {code for code, _ in desired}
        for code in existing - desired_codes:
            delete_fn(self.conn, code, commit=commit)
        for code, name in sorted(desired):
            upsert_fn(code, name)
