"""database/grocery_db.py — SQLite grocery inventory with expiry tracking."""

import sqlite3
import os
from datetime import datetime, timedelta
from typing import List, Optional, Dict


class GroceryDatabase:
    """
    SQLite-backed pantry store.

    Key design decisions
    --------------------
    - item_name is UNIQUE → adding an existing item **accumulates** quantity
    - expiry_date stored as ISO-8601 string (SQLite TEXT affinity)
    - All public methods return plain dicts — no ORM leakage
    """

    def __init__(self, db_path: str = "data/grocery_inventory.db"):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db_path = db_path
        # check_same_thread=False is safe here because Streamlit is single-threaded
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row          # enables dict-like access
        self.conn.execute("PRAGMA journal_mode=WAL")  # better concurrency
        self._initialize()

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------
    def _initialize(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS grocery_inventory (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                item_name     TEXT    NOT NULL UNIQUE,
                quantity      REAL    NOT NULL DEFAULT 1,
                unit          TEXT    NOT NULL DEFAULT 'pieces',
                category      TEXT,
                is_perishable INTEGER NOT NULL DEFAULT 0,
                purchase_date TEXT    DEFAULT (datetime('now')),
                expiry_date   TEXT,
                last_updated  TEXT    DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS pantry_log (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                action     TEXT NOT NULL,          -- 'add' | 'remove' | 'clear'
                item_name  TEXT,
                quantity   REAL,
                unit       TEXT,
                note       TEXT,
                ts         TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS meal_plans (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                plan_date   DATE    NOT NULL,
                meal_type   TEXT    NOT NULL,
                recipe_name TEXT    NOT NULL,
                calories    INTEGER DEFAULT 0,
                protein_g   REAL    DEFAULT 0,
                carbs_g     REAL    DEFAULT 0,
                fat_g       REAL    DEFAULT 0,
                notes       TEXT,
                created_at  TEXT    DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS conversation_history (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                user_query      TEXT NOT NULL,
                recipe_name     TEXT,
                ingredients_used TEXT,
                timestamp       TEXT DEFAULT (datetime('now'))
            );
        """)
        self.conn.commit()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _rows_to_dicts(self, rows) -> List[Dict]:
        return [dict(row) for row in rows]

    def _log(self, action: str, item_name: str = None,
             quantity: float = None, unit: str = None, note: str = None):
        try:
            self.conn.execute(
                "INSERT INTO pantry_log (action, item_name, quantity, unit, note) "
                "VALUES (?, ?, ?, ?, ?)",
                (action, item_name, quantity, unit, note),
            )
            self.conn.commit()
        except Exception:
            pass  # logging must never crash the main flow

    # ------------------------------------------------------------------
    # ADD / UPDATE
    # ------------------------------------------------------------------
    def add_grocery(
        self,
        item_name: str,
        quantity: float,
        unit: str,
        category: str = None,
        is_perishable: bool = False,
        days_until_expiry: int = None,
        expiry_date: str = None,   # accept pre-computed ISO string too
    ) -> bool:
        """
        Add a grocery item or accumulate quantity if it already exists.

        Parameters
        ----------
        item_name       : canonical singular lowercase name
        quantity        : numeric amount
        unit            : 'g' | 'kg' | 'ml' | 'l' | 'pieces' | etc.
        category        : 'vegetables' | 'fruits' | 'dairy' | 'proteins' |
                          'grains' | 'spices' | 'oils' | 'other'
        is_perishable   : True for fresh items
        days_until_expiry : days from now until expiry (int)
        expiry_date     : ISO-8601 string — alternative to days_until_expiry

        Returns True on success, False on failure.
        """
        name = item_name.lower().strip()

        # Resolve expiry date
        resolved_expiry: Optional[str] = None
        if expiry_date:
            resolved_expiry = expiry_date
        elif days_until_expiry and days_until_expiry > 0:
            resolved_expiry = (
                datetime.now() + timedelta(days=int(days_until_expiry))
            ).isoformat(timespec="seconds")

        try:
            self.conn.execute(
                """
                INSERT INTO grocery_inventory
                    (item_name, quantity, unit, category, is_perishable, expiry_date)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(item_name) DO UPDATE SET
                    quantity     = quantity + excluded.quantity,
                    unit         = excluded.unit,
                    category     = COALESCE(excluded.category, category),
                    is_perishable = excluded.is_perishable,
                    expiry_date  = COALESCE(excluded.expiry_date, expiry_date),
                    last_updated = datetime('now')
                """,
                (name, quantity, unit, category, 1 if is_perishable else 0, resolved_expiry),
            )
            self.conn.commit()
            self._log("add", name, quantity, unit)
            return True
        except Exception as e:
            print(f"[GroceryDB] add_grocery error: {e}")
            return False

    # ------------------------------------------------------------------
    # READ
    # ------------------------------------------------------------------
    def get_all_groceries(self) -> List[Dict]:
        """Return all items with quantity > 0, sorted by name."""
        cur = self.conn.execute(
            "SELECT * FROM grocery_inventory WHERE quantity > 0 ORDER BY item_name"
        )
        return self._rows_to_dicts(cur.fetchall())

    def get_grocery_by_name(self, item_name: str) -> Optional[Dict]:
        """Exact-match lookup (case-insensitive)."""
        cur = self.conn.execute(
            "SELECT * FROM grocery_inventory WHERE item_name = ?",
            (item_name.lower().strip(),),
        )
        row = cur.fetchone()
        return dict(row) if row else None

    def search_grocery(self, query: str) -> List[Dict]:
        """Fuzzy LIKE search — useful for partial name matching."""
        cur = self.conn.execute(
            "SELECT * FROM grocery_inventory WHERE item_name LIKE ? AND quantity > 0",
            (f"%{query.lower().strip()}%",),
        )
        return self._rows_to_dicts(cur.fetchall())

    def get_expiring_soon(self, days: int = 3) -> List[Dict]:
        """Items expiring within `days` days (including already expired)."""
        cutoff = (datetime.now() + timedelta(days=days)).isoformat(timespec="seconds")
        cur = self.conn.execute(
            """
            SELECT * FROM grocery_inventory
            WHERE expiry_date IS NOT NULL
              AND expiry_date <= ?
              AND quantity > 0
            ORDER BY expiry_date
            """,
            (cutoff,),
        )
        return self._rows_to_dicts(cur.fetchall())

    def get_by_category(self, category: str) -> List[Dict]:
        cur = self.conn.execute(
            "SELECT * FROM grocery_inventory WHERE category = ? AND quantity > 0",
            (category.lower(),),
        )
        return self._rows_to_dicts(cur.fetchall())

    # ------------------------------------------------------------------
    # UPDATE
    # ------------------------------------------------------------------
    def update_quantity(self, item_name: str, new_quantity: float) -> bool:
        """
        Overwrite quantity. If new_quantity <= 0, effectively marks as used up
        but keeps the row (soft-delete pattern).
        """
        name = item_name.lower().strip()
        cur = self.conn.execute(
            "UPDATE grocery_inventory SET quantity = ?, last_updated = datetime('now') "
            "WHERE item_name = ?",
            (max(new_quantity, 0), name),
        )
        self.conn.commit()
        if cur.rowcount:
            self._log("update", name, new_quantity)
        return cur.rowcount > 0

    # ------------------------------------------------------------------
    # DELETE
    # ------------------------------------------------------------------
    def delete_grocery(self, item_name: str) -> bool:
        """
        Hard-delete by exact name, then fuzzy if exact misses.
        Returns True if at least one row was deleted.
        """
        name = item_name.lower().strip()

        # 1. Exact match
        cur = self.conn.execute(
            "DELETE FROM grocery_inventory WHERE item_name = ?", (name,)
        )
        self.conn.commit()

        if cur.rowcount:
            self._log("remove", name)
            return True

        # 2. Fuzzy fallback (contains)
        cur = self.conn.execute(
            "DELETE FROM grocery_inventory WHERE item_name LIKE ?",
            (f"%{name}%",),
        )
        self.conn.commit()

        if cur.rowcount:
            self._log("remove", name, note="fuzzy match")
        return cur.rowcount > 0

    def delete_many(self, item_names: List[str]) -> Dict[str, bool]:
        """Delete multiple items. Returns {name: success} map."""
        return {name: self.delete_grocery(name) for name in item_names}

    def clear_inventory(self) -> int:
        """Remove ALL items. Returns count of deleted rows."""
        cur = self.conn.execute("SELECT COUNT(*) FROM grocery_inventory")
        count = cur.fetchone()[0]
        self.conn.execute("DELETE FROM grocery_inventory")
        self.conn.commit()
        self._log("clear", note=f"cleared {count} items")
        return count

    # ------------------------------------------------------------------
    # MEAL PLANS
    # ------------------------------------------------------------------
    def save_meal_plan(
        self,
        plan_date: str,
        meal_type: str,
        recipe_name: str,
        calories: int = 0,
        protein_g: float = 0,
        carbs_g: float = 0,
        fat_g: float = 0,
        notes: str = "",
    ) -> bool:
        try:
            self.conn.execute(
                """
                INSERT INTO meal_plans
                    (plan_date, meal_type, recipe_name, calories, protein_g, carbs_g, fat_g, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (plan_date, meal_type, recipe_name, calories, protein_g, carbs_g, fat_g, notes),
            )
            self.conn.commit()
            return True
        except Exception as e:
            print(f"[GroceryDB] save_meal_plan error: {e}")
            return False

    def get_meal_plans(self, days: int = 7) -> List[Dict]:
        cur = self.conn.execute(
            """
            SELECT * FROM meal_plans
            WHERE plan_date >= date('now', ?)
            ORDER BY plan_date DESC, meal_type
            """,
            (f"-{days} days",),
        )
        return self._rows_to_dicts(cur.fetchall())

    def get_meal_plans_today(self) -> List[Dict]:
        cur = self.conn.execute(
            "SELECT * FROM meal_plans WHERE plan_date = date('now') ORDER BY meal_type"
        )
        return self._rows_to_dicts(cur.fetchall())

    # ------------------------------------------------------------------
    # CONVERSATION HISTORY
    # ------------------------------------------------------------------
    def save_conversation(
        self, user_query: str, recipe_name: str = "", ingredients_used: str = ""
    ):
        try:
            self.conn.execute(
                "INSERT INTO conversation_history (user_query, recipe_name, ingredients_used) "
                "VALUES (?, ?, ?)",
                (user_query, recipe_name, ingredients_used),
            )
            self.conn.commit()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # STATS / DIAGNOSTICS
    # ------------------------------------------------------------------
    def get_stats(self) -> Dict:
        """Quick summary stats for the sidebar."""
        total   = self.conn.execute("SELECT COUNT(*) FROM grocery_inventory WHERE quantity > 0").fetchone()[0]
        expired = len(self.get_expiring_soon(days=0))
        soon    = len(self.get_expiring_soon(days=3))
        cats    = self.conn.execute(
            "SELECT category, COUNT(*) c FROM grocery_inventory WHERE quantity > 0 GROUP BY category"
        ).fetchall()
        return {
            "total": total,
            "expired": expired,
            "expiring_soon": soon,
            "by_category": {row[0]: row[1] for row in cats},
        }

    def close(self):
        self.conn.close()