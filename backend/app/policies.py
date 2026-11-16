"""Demo users and per-role data policy. Replace USERS with a real user store (hashed passwords)."""
USERS = {"admin": ("admin123", "admin"), "analyst": ("analyst123", "analyst"), "junior": ("junior123", "junior_analyst")}
POLICY = {
    "admin": {"deny_tables": set(), "deny_cols": {}},
    "analyst": {"deny_tables": {"employees"}, "deny_cols": {}},
    "junior_analyst": {"deny_tables": {"employees"}, "deny_cols": {"customers": {"email", "phone"}}},
}
