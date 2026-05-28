"""
DATABASE.py
-----------
Thin wrapper around the original `DB` class from `dhanak.py`.

The WebChannel bridge and Qt/HTML frontend talk to this module instead of
opening SQLite connections directly. This keeps the CustomTkinter backend
as the single source of truth for:
  - schema
  - business rules (availability checks, tax calculation, audit log, etc.)
"""

from typing import Any, Dict, List, Optional

from dhanak import DB


class Database:
    """
    High‑level database façade.

    Internally uses `dhanak.DB` but exposes methods in a shape that is
    convenient for the HTML/JS frontend (via the `Bridge`).
    """

    def __init__(self) -> None:
        self.engine = DB()

    # ──────────────────────────── Bookings ────────────────────────────────
    def get_all_bookings(self, search: str = "", status_filter: str = "all") -> List[Dict[str, Any]]:
        from run import get_backend  # local import to avoid cycles at import time

        backend = get_backend()
        return backend.list_bookings(search=search, status_filter=status_filter)

    def add_booking(self, data: Dict[str, Any]) -> Dict[str, Any]:
        from run import get_backend

        backend = get_backend()
        return backend.create_booking(data)

    def update_booking(self, booking_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        from run import get_backend

        backend = get_backend()
        return backend.update_booking(booking_id, data)

    def cancel_booking(self, booking_id: int) -> Dict[str, Any]:
        from run import get_backend

        backend = get_backend()
        return backend.cancel_booking(booking_id)

    def clear_booking(self, booking_id: int) -> Dict[str, Any]:
        from run import get_backend

        backend = get_backend()
        return backend.mark_cleared(booking_id)

    def get_booking_by_id(self, booking_id: int) -> Optional[Dict[str, Any]]:
        row = self.engine.get(booking_id)
        return dict(row) if row else None

    # ──────────────────────────── Dashboard / views ───────────────────────
    def get_stats(self) -> Dict[str, Any]:
        from run import get_backend

        backend = get_backend()
        return backend.get_stats()

    def get_customers(self) -> List[Dict[str, Any]]:
        from run import get_backend

        backend = get_backend()
        return backend.get_customers()

    def get_upcoming(self) -> List[Dict[str, Any]]:
        from run import get_backend

        backend = get_backend()
        return backend.get_upcoming()

    def get_report_data(self) -> Dict[str, Any]:
        from run import get_backend

        backend = get_backend()
        return backend.get_report_data()

    # ──────────────────────────── Calendar / summaries ─────────────────────
    def get_month_availability(self, year: int, month: int) -> Dict[str, Any]:
        from run import get_backend

        backend = get_backend()
        return backend.get_month_availability(year, month)

    def get_day_availability(self, date_str: str) -> Dict[str, Any]:
        from run import get_backend

        backend = get_backend()
        return backend.get_day_availability(date_str)

    def get_monthly_summary(self, year: int, month: int) -> Dict[str, Any]:
        from run import get_backend

        backend = get_backend()
        return backend.get_monthly_summary(year, month)

    def get_yearly_summary(self, year: int) -> Dict[str, Any]:
        from run import get_backend

        backend = get_backend()
        return backend.get_yearly_summary(year)

    # ──────────────────────────── FPH Menus ────────────────────────────────
    def save_fph_menu(self, data: dict) -> dict:
        return self.engine.save_fph_menu(data)

    def get_fph_menus(self) -> list:
        return self.engine.get_fph_menus()

    def get_fph_menu_by_booking(self, booking_id: int):
        return self.engine.get_fph_menu_by_booking(booking_id)

    def get_cancelled_bookings(self) -> list:
        return self.engine.get_cancelled_bookings()

    def delete_fph_menu(self, menu_id: int) -> dict:
        """
        Delete a single FPH menu record by its primary key id.
        Frontends can use this to 'reset' or remove a mistaken FPH menu
        while still allowing multiple menus over time for the same booking.
        """
        return self.engine.delete_fph_menu(menu_id)

