from datetime import date

import pytest

from sn_manager.core.version_a import (
    SnFields,
    decode_version_a,
    encode_version_a,
    month_to_code,
    day_to_code,
)


def test_encode_prd_example():
    fields = SnFields(
        version="A",
        product_model="SVG14",
        hw_batch="05",
        factory="2",
        market="1",
        prod_year=2026,
        prod_month=12,
        prod_day=1,
        seq=0xF04,
    )
    assert encode_version_a(fields) == "ASVG140521261CF04"


def test_decode_prd_example():
    f = decode_version_a("ASVG140521261CF04")
    assert f.product_model == "SVG14"
    assert f.prod_year == 2026
    assert f.prod_month == 12
    assert f.prod_day == 1
    assert f.seq == 0xF04


def test_roundtrip_month_day_boundaries():
    for month in range(1, 13):
        for day in (1, 9, 10, 30, 31):
            if month == 2 and day > 29:
                continue
            if month in (4, 6, 9, 11) and day > 30:
                continue
            try:
                date(2026, month, day)
            except ValueError:
                continue
            fields = SnFields(
                version="A",
                product_model="ABC12",
                hw_batch="01",
                factory="1",
                market="0",
                prod_year=2026,
                prod_month=month,
                prod_day=day,
                seq=0,
            )
            assert decode_version_a(encode_version_a(fields)) == fields


def test_reject_bad_length():
    with pytest.raises(Exception):
        decode_version_a("SHORT")


def test_seq_fff():
    fields = SnFields(
        version="A",
        product_model="ABC12",
        hw_batch="01",
        factory="1",
        market="0",
        prod_year=2026,
        prod_month=1,
        prod_day=1,
        seq=0xFFF,
    )
    assert encode_version_a(fields).endswith("FFF")
