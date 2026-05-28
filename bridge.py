import json
from PySide6.QtCore import QObject, Slot

from database import Database
from run import get_backend


class Bridge(QObject):
    """
    Exposes Python backend methods to the HTML/JS frontend via Qt WebChannel.

    In JavaScript you call:
        backend.some_method(arg1, arg2, callbackFn)

    and receive a JSON string which you then `JSON.parse(...)`.
    """

    def __init__(self) -> None:
        super().__init__()
        self.db = Database()
        self.backend = get_backend()

    # ──────────────────────────── Bookings ────────────────────────────────
    @Slot(result=str)
    def get_bookings(self) -> str:
        return json.dumps(self.db.get_all_bookings())

    @Slot(str, str, result=str)
    def get_bookings_filtered(self, search: str, status: str) -> str:
        return json.dumps(self.db.get_all_bookings(search=search, status_filter=status))

    @Slot(str, result=str)
    def add_booking(self, data_json: str) -> str:
        try:
            data = json.loads(data_json)
            res = self.db.add_booking(data)
            return json.dumps(res)
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @Slot(int, str, result=str)
    def update_booking(self, booking_id: int, data_json: str) -> str:
        try:
            data = json.loads(data_json)
            res = self.db.update_booking(booking_id, data)
            return json.dumps(res)
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @Slot(int, result=str)
    def cancel_booking(self, booking_id: int) -> str:
        try:
            res = self.db.cancel_booking(booking_id)
            return json.dumps(res)
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @Slot(int, result=str)
    def clear_booking(self, booking_id: int) -> str:
        try:
            res = self.db.clear_booking(booking_id)
            return json.dumps(res)
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @Slot(int, float, float, result=str)
    def mark_cleared_with_charges(self, booking_id: int, discount: float, seating: float) -> str:
        """
        Mark a booking cleared, saving discount and extra seating charge.
        Called from the JS charges modal before printing.
        """
        try:
            res = self.backend.mark_cleared_with_charges(booking_id, discount, seating)
            return json.dumps(res)
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @Slot(int, float, float, result=str)
    def print_clearance_receipt_with_charges(self, booking_id: int, discount: float, seating: float) -> str:
        """
        Print/open the clearance receipt, applying discount and extra seating charge.
        """
        try:
            res = self.backend.print_clearance_receipt_with_charges(booking_id, discount, seating)
            return json.dumps(res)
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    # ──────────────────────────── Dashboard ───────────────────────────────
    @Slot(result=str)
    def get_stats(self) -> str:
        return json.dumps(self.db.get_stats())

    # ──────────────────────────── Other views ─────────────────────────────
    @Slot(result=str)
    def get_customers(self) -> str:
        return json.dumps(self.db.get_customers())

    @Slot(result=str)
    def get_upcoming(self) -> str:
        return json.dumps(self.db.get_upcoming())

    @Slot(result=str)
    def get_report_data(self) -> str:
        return json.dumps(self.db.get_report_data())

    @Slot(int, int, result=str)
    def get_monthly_summary(self, year: int, month: int) -> str:
        """
        Monthly summary wrapper around DhanakBackend.get_monthly_summary.
        """
        res = self.backend.get_monthly_summary(year, month)
        return json.dumps(res)

    @Slot(int, result=str)
    def get_yearly_summary(self, year: int) -> str:
        """
        Yearly summary wrapper around DhanakBackend.get_yearly_summary.
        """
        res = self.backend.get_yearly_summary(year)
        return json.dumps(res)

    # ──────────────────────────── Calendar / availability ──────────────────
    @Slot(str, result=str)
    def get_day_availability(self, date_str: str) -> str:
        """
        Availability for a single day (yyyy-mm-dd) using DB.availability.
        """
        res = self.backend.get_day_availability(date_str)
        return json.dumps(res)

    @Slot(int, int, result=str)
    def get_month_availability(self, year: int, month: int) -> str:
        """
        Month availability for the calendar tab (uses DB.month_avail).
        """
        res = self.backend.get_month_availability(year, month)
        return json.dumps(res)

    # ──────────────────────────── Search / history ────────────────────────
    @Slot(str, result=str)
    def customer_history(self, phone: str) -> str:
        """
        Return a booking history for the given phone number.

        JS:
          backend.customer_history(phone, (json) => { ... });
        """
        res = self.backend.customer_history(phone)
        return json.dumps(res)

    @Slot(str, bool, result=str)
    def search_bookings(self, query: str, include_cancelled: bool = False) -> str:
        """
        Full‑text booking search using DB.search.

        JS:
          backend.search_bookings(q, false, (json) => { ... });
        """
        res = self.backend.search_bookings(query, include_cancelled)
        return json.dumps(res)

    # ──────────────────────────── Backup / exports ────────────────────────
    @Slot(result=str)
    def backup_now(self) -> str:
        """
        Trigger a SQLite backup. Returns backup path or an error.
        """
        res = self.backend.backup_now()
        return json.dumps(res)

    @Slot(result=str)
    def export_csv(self) -> str:
        """
        Export bookings to CSV in the local 'exports' folder.
        """
        res = self.backend.export_csv()
        return json.dumps(res)

    @Slot(str, str, result=str)
    def sync_google_sheet(self, sheet_id: str, key_path: str) -> str:
        """
        Headless Google Sheets sync using service account credentials.
        """
        res = self.backend.sync_google_sheet(sheet_id, key_path)
        return json.dumps(res)

    # ──────────────────────────── Receipts ────────────────────────────────
    @Slot(int, result=str)
    def print_booking_receipt(self, booking_id: int) -> str:
        """
        Generate & open the HTML thermal receipt for a booking.

        JS usage example:
            backend.print_booking_receipt(id, (json) => {
              const r = JSON.parse(json);
              if (!r.success) alert(r.error);
            });
        """
        try:
            res = self.backend.print_booking_receipt(booking_id)
            return json.dumps(res)
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @Slot(int, result=str)
    def print_clearance_receipt(self, booking_id: int) -> str:
        """
        Generate & open the A4 clearance receipt for a booking.
        """
        try:
            res = self.backend.print_clearance_receipt(booking_id)
            return json.dumps(res)
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @Slot(int, str, result=str)
    def save_clearance_pdf(self, booking_id: int, path: str) -> str:
        """
        Generate an A4 PDF clearance receipt at the given path.
        """
        try:
            res = self.backend.save_clearance_pdf(booking_id, path)
            return json.dumps(res)
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    # ──────────────────────────── Voice / AI ──────────────────────────────
    @Slot(result=str)
    def voice_interact(self) -> str:
        """
        Run a single microphone → AI → speaker cycle using the legacy
        `Voice` helper from `dhanak.py`.

        JS usage example (AI tab):
            backend.voice_interact((json) => {
              const r = JSON.parse(json);
              // show r.heard and r.reply in the UI
            });
        """
        res = self.backend.voice_interact()
        return json.dumps(res)

    @Slot(str, result=str)
    def ai_query(self, text: str) -> str:
        """
        Text‑only AI assistant endpoint (no microphone / TTS).

        JS:
          backend.ai_query(userText, (json) => { ... });
        """
        res = self.backend.ai_query(text)
        return json.dumps(res)

    # ──────────────────────────── Config / Settings ────────────────────────
    @Slot(str, result=str)
    def get_config_value(self, key: str) -> str:
        """
        Read a single key from the Config backend.
        """
        value = self.backend.get_config_value(key)
        return json.dumps({"key": key, "value": value})

    @Slot(str, str, result=str)
    def set_config_value(self, key: str, value: str) -> str:
        """
        Persist a single Config key (hall_name, api_key, gsheet_id, etc.).
        """
        res = self.backend.set_config_value(key, value)
        return json.dumps(res)


    # ──────────────────────────── FPH Menu ────────────────────────────────
    @Slot(str, result=str)
    def save_fph_menu(self, data_json: str) -> str:
        """Save a Food-Per-Head menu selection for a booking."""
        try:
            data = json.loads(data_json)
            res  = self.db.save_fph_menu(data)
            return json.dumps(res)
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @Slot(result=str)
    def get_fph_menus(self) -> str:
        """Return all saved FPH menu records."""
        try:
            return json.dumps(self.db.get_fph_menus())
        except Exception as e:
            return json.dumps([])

    @Slot(int, result=str)
    def get_fph_menu_by_booking(self, booking_id: int) -> str:
        """Return the latest FPH menu for a booking."""
        try:
            res = self.db.get_fph_menu_by_booking(booking_id)
            return json.dumps(res or {})
        except Exception as e:
            return json.dumps({})

    @Slot(int, result=str)
    def delete_fph_menu(self, menu_id: int) -> str:
        """Delete a single FPH menu record by its id."""
        try:
            res = self.db.delete_fph_menu(menu_id)
            return json.dumps(res)
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    # ──────────────────────────── Cancelled log ────────────────────────────
    @Slot(result=str)
    def get_cancelled_bookings(self) -> str:
        """Return all cancelled bookings for the history log."""
        try:
            return json.dumps(self.db.get_cancelled_bookings())
        except Exception as e:
            return json.dumps([])

    @Slot(str, result=str)
    def print_fph_menu(self, data_json: str) -> str:
        """Generate and open/print an A4 FPH menu sheet."""
        try:
            import json as _json
            data = _json.loads(data_json)
            res  = self.backend.print_fph_menu(data)
            return _json.dumps(res)
        except Exception as e:
            return __import__('json').dumps({"success": False, "error": str(e)})
