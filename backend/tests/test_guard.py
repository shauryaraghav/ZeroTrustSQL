import os, sys
import pytest
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from app.guard import validate, Rejected

T = {"orders", "customers", "products", "order_items"}
JUNIOR = {"customers": {"email", "phone"}}


@pytest.mark.parametrize("sql", [
    "DROP TABLE orders", "SELECT 1; DELETE FROM orders", "UPDATE orders SET status='x'",
    "SELECT pg_sleep(10)", "SELECT * FROM pg_shadow", "SELECT * INTO x FROM orders",
    "WITH d AS (DELETE FROM orders RETURNING *) SELECT * FROM d",
    "SELECT * FROM information_schema.tables", "SELECT * FROM employees",
])
def test_blocked(sql):
    with pytest.raises(Rejected):
        validate(sql, T, 500)


def test_limit_injected():
    assert validate("SELECT id FROM orders", T, 500).endswith("LIMIT 500")


def test_cte_allowed():
    validate("WITH t AS (SELECT customer_id FROM orders) SELECT * FROM t", T, 500)


@pytest.mark.parametrize("sql", [
    "SELECT email FROM customers", "SELECT c.phone FROM customers c", "SELECT * FROM customers",
    "SELECT c.* FROM customers c", "WITH x AS (SELECT email FROM customers) SELECT * FROM x",
])
def test_column_rbac_blocked(sql):
    with pytest.raises(Rejected):
        validate(sql, T, 500, JUNIOR)


def test_column_rbac_allowed():
    validate("SELECT name, country FROM customers", T, 500, JUNIOR)
    validate("SELECT count(*) FROM customers", T, 500, JUNIOR)
