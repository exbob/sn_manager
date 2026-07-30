from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from sn_manager.core.errors import ValidationError

SN_LENGTH = 17
VERSION_A = "A"

MONTH_CODES = "123456789ABC"
DAY_CODES = "123456789ABCDEFGHIJKLMNOPQRSTUV"

_ALNUM = re.compile(r"^[A-Z0-9]+$")


@dataclass(frozen=True, eq=True)
class SnFields:
    version: str
    product_model: str
    hw_batch: str
    factory: str
    market: str
    prod_year: int
    prod_month: int
    prod_day: int
    seq: int


@dataclass(frozen=True, eq=True)
class GenerationInput:
    """validate_generation_input 返回的规范化生成参数。"""

    version: str
    product_model: str
    hw_batch: str
    factory: str
    market: str
    prod_date: date


def month_to_code(month: int) -> str:
    if not 1 <= month <= 12:
        raise ValidationError(f"无效月份: {month}")
    return MONTH_CODES[month - 1]


def day_to_code(day: int) -> str:
    if not 1 <= day <= 31:
        raise ValidationError(f"无效日期: {day}")
    return DAY_CODES[day - 1]


def _code_to_month(code: str) -> int:
    idx = MONTH_CODES.find(code)
    if idx < 0:
        raise ValidationError(f"无效月份编码: {code}")
    return idx + 1


def _code_to_day(code: str) -> int:
    idx = DAY_CODES.find(code)
    if idx < 0:
        raise ValidationError(f"无效日期编码: {code}")
    return idx + 1


def _normalize_alnum(value: str, field_name: str, length: int) -> str:
    normalized = value.strip().upper()
    if len(normalized) != length:
        raise ValidationError(f"{field_name}长度必须为{length}")
    if not _ALNUM.match(normalized):
        raise ValidationError(f"{field_name}只能包含字母和数字")
    return normalized


def validate_generation_input(
    *,
    product_model: str,
    hw_batch: str,
    factory: str,
    market: str,
    prod_date: date,
) -> GenerationInput:
    """校验生成输入并返回规范化分量。"""
    return GenerationInput(
        version=VERSION_A,
        product_model=_normalize_alnum(product_model, "产品型号", 5),
        hw_batch=_normalize_alnum(hw_batch, "硬件批次", 2),
        factory=_normalize_alnum(factory, "生产单位", 1),
        market=_normalize_alnum(market, "投放市场", 1),
        prod_date=prod_date,
    )


def _validate_fields(fields: SnFields) -> None:
    if fields.version != VERSION_A:
        raise ValidationError(f"不支持的 SN 版本: {fields.version}")
    _normalize_alnum(fields.product_model, "产品型号", 5)
    _normalize_alnum(fields.hw_batch, "硬件批次", 2)
    _normalize_alnum(fields.factory, "生产单位", 1)
    _normalize_alnum(fields.market, "投放市场", 1)
    if fields.prod_year < 2000:
        raise ValidationError(f"无效生产年份: {fields.prod_year}")
    try:
        date(fields.prod_year, fields.prod_month, fields.prod_day)
    except ValueError as exc:
        raise ValidationError("无效生产日期") from exc
    if not 0 <= fields.seq <= 0xFFF:
        raise ValidationError(f"序号超出范围: {fields.seq}")


def encode_version_a(fields: SnFields) -> str:
    _validate_fields(fields)
    year_part = f"{fields.prod_year % 100:02d}"
    day_part = day_to_code(fields.prod_day)
    month_part = month_to_code(fields.prod_month)
    seq_part = f"{fields.seq:03X}"
    return (
        f"{fields.version}"
        f"{fields.product_model.upper()}"
        f"{fields.hw_batch.upper()}"
        f"{fields.factory.upper()}"
        f"{fields.market.upper()}"
        f"{year_part}"
        f"{day_part}"
        f"{month_part}"
        f"{seq_part}"
    )


def decode_version_a(sn: str) -> SnFields:
    if len(sn) != SN_LENGTH:
        raise ValidationError(f"SN 长度必须为{SN_LENGTH}，实际为{len(sn)}")

    version = sn[0]
    if version != VERSION_A:
        raise ValidationError(f"不支持的 SN 版本: {version}")

    product_model = sn[1:6]
    hw_batch = sn[6:8]
    factory = sn[8]
    market = sn[9]
    year_part = sn[10:12]
    day_code = sn[12]
    month_code = sn[13]
    seq_part = sn[14:17]

    for label, value, length in (
        ("产品型号", product_model, 5),
        ("硬件批次", hw_batch, 2),
        ("生产单位", factory, 1),
        ("投放市场", market, 1),
    ):
        if len(value) != length or not _ALNUM.match(value):
            raise ValidationError(f"无效{label}: {value}")

    if not year_part.isdigit():
        raise ValidationError(f"无效年份: {year_part}")
    prod_year = 2000 + int(year_part)

    prod_month = _code_to_month(month_code)
    prod_day = _code_to_day(day_code)

    try:
        date(prod_year, prod_month, prod_day)
    except ValueError as exc:
        raise ValidationError("无效生产日期") from exc

    try:
        seq = int(seq_part, 16)
    except ValueError as exc:
        raise ValidationError(f"无效序号: {seq_part}") from exc
    if not 0 <= seq <= 0xFFF:
        raise ValidationError(f"序号超出范围: {seq_part}")

    return SnFields(
        version=version,
        product_model=product_model,
        hw_batch=hw_batch,
        factory=factory,
        market=market,
        prod_year=prod_year,
        prod_month=prod_month,
        prod_day=prod_day,
        seq=seq,
    )
