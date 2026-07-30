"""SQLite DDL 与种子数据 SQL。"""

DDL = """
CREATE TABLE IF NOT EXISTS product_models (
    code TEXT PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS hardware_batches (
    code TEXT PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS factories (
    code TEXT PRIMARY KEY,
    name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS markets (
    code TEXT PRIMARY KEY,
    name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS serial_numbers (
    sn TEXT PRIMARY KEY,
    version TEXT NOT NULL,
    product_model TEXT NOT NULL,
    hw_batch TEXT NOT NULL,
    factory TEXT NOT NULL,
    market TEXT NOT NULL,
    prod_year INTEGER NOT NULL,
    prod_month INTEGER NOT NULL,
    prod_day INTEGER NOT NULL,
    seq INTEGER NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (product_model, hw_batch, prod_year, prod_month, prod_day, seq)
);

CREATE INDEX IF NOT EXISTS idx_serial_numbers_dimension
    ON serial_numbers (product_model, hw_batch, prod_year, prod_month, prod_day);

CREATE INDEX IF NOT EXISTS idx_serial_numbers_status
    ON serial_numbers (status);
"""

SEED = """
INSERT OR IGNORE INTO factories (code, name) VALUES ('1', '自己生产');
INSERT OR IGNORE INTO factories (code, name) VALUES ('2', '赛威思');

INSERT OR IGNORE INTO markets (code, name) VALUES ('0', '不限');
INSERT OR IGNORE INTO markets (code, name) VALUES ('1', '中国');
INSERT OR IGNORE INTO markets (code, name) VALUES ('2', '韩国');
INSERT OR IGNORE INTO markets (code, name) VALUES ('3', '美国');
"""
