                                    
                                                   

import os, sys, json, re, shutil, datetime, calendar, threading, sqlite3, subprocess, math
import tkinter as tk
from tkinter import messagebox, ttk, filedialog

                                                                      
import customtkinter as ctk

                                                                      
try:
    import anthropic;       CLAUDE_OK = True
except ImportError:         CLAUDE_OK = False

try:
    import speech_recognition as sr; SR_OK = True
except ImportError:                  SR_OK = False

try:
    import pyttsx3;         TTS_OK = True
except ImportError:         TTS_OK = False

try:
    import edge_tts;        EDGE_TTS_OK = True
except ImportError:         EDGE_TTS_OK = False

import asyncio
import tempfile

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units    import cm
    from reportlab.lib          import colors
    from reportlab.platypus     import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.platypus     import BaseDocTemplate, PageTemplate, Frame
    from reportlab.lib.styles   import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums    import TA_CENTER, TA_LEFT, TA_RIGHT
    PDF_OK = True
except ImportError:         PDF_OK = False

try:
    from PIL import Image as PILImage
    PIL_OK = True
except ImportError:
    PIL_OK = False

try:
    import gspread
    from google.oauth2.service_account import Credentials
    GSPREAD_OK = True
except ImportError:
    GSPREAD_OK = False

APP_NAME    = "Dhanak Banquet Hall Manager"
APP_VER     = "v3.0"
DB_FILE     = "dhanak_bookings.db"
CFG_FILE    = "dhanak_config.json"
BACKUP_DIR  = "backups"
RECEIPTS_DIR= "receipts"

                                                                      
                                                                    
GOLD        = "#C6A058"  # Accent Metal / Primary action
GOLD_H      = "#A38446"  # Hover for gold
GOLD_DK     = "#8C6D33"  # Deeper gold / dividers

# Old Money dark palette
BG          = "#04122D"  # Main background
PANEL       = "#0A1429"  # Primary surface (top bar / side panels)
CARD        = "#0D1A35"  # Card foreground
CARD2       = "#101F3D"  # Slightly lighter card
BORDER      = "#C6A058"  # Gold framing

WHITE       = "#F9FAFF"  # Primary text
MUTED       = "#A5B4FC"  # Secondary text

# Status / accent colors
GREEN       = "#7ED0B1"  # Minty cleared status
RED         = "#DC2626"
ORANGE      = "#D58661"  # Copper for warnings / pending
BLUE        = "#4F46E5"
PURPLE_GLOW = "#151B32"

MONTHS      = ["January","February","March","April","May","June",
               "July","August","September","October","November","December"]
SHIFTS      = ["Day 1", "Day 2", "Night 1", "Night 2"]
EVENT_TYPES = ["Mehndi","Baraat","Walima","Birthday","Conference","Other"]
MENU_TYPES  = ["FPH", "SPH"]
FILER_OPTS  = ["Non-Filer", "Filer"]

                                                                      
         
                                                                      

class Config:
    DEFAULTS = {
        "api_key":           "",
        "hall_name":         "Dhanak Banquet Hall",
        "hall_address":      "Khanewal, Pakistan",
        "hall_phone1":       "03356880079",
        "hall_phone2":       "03006880079",
        "hall_ntn":          "",
        "hall_strn":         "",
        "gsheet_id":         "",
        "gsheet_key_path":   "",
        "thermal_printer":   "",   # Windows printer name for 80mm thermal
        "a4_printer":        "",   # Windows printer name for A4 clearance
        "dark_mode":         "0",  # "1" = dark, "0" = light
    }

    def __init__(self):
        self.data = dict(self.DEFAULTS)
        if os.path.exists(CFG_FILE):
            try:
                with open(CFG_FILE) as f:
                    self.data.update(json.load(f))
            except Exception:
                pass

    def get(self, k, default=""):
        return self.data.get(k, default)

    def set(self, k, v):
        self.data[k] = v
        with open(CFG_FILE, "w") as f:
            json.dump(self.data, f, indent=2)

                                                                      
           
                                                                      

class DB:
    def __init__(self, path=DB_FILE):
        self.path = path
        self.cx   = sqlite3.connect(path, check_same_thread=False)
        self.cx.row_factory = sqlite3.Row
        self._init()

    def _init(self):
        self.cx.executescript("""
        PRAGMA journal_mode=WAL;

        CREATE TABLE IF NOT EXISTS bookings (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_name TEXT    NOT NULL,
            cnic          TEXT    DEFAULT "",
            phone         TEXT    DEFAULT "",
            booking_time  TEXT    NOT NULL,
            event_date    TEXT    NOT NULL,
            shift         TEXT    NOT NULL,
            persons       INTEGER DEFAULT 0,
            menu_type     TEXT    DEFAULT "FPH",
            event_type    TEXT    DEFAULT "Mehndi",
            rate          REAL    DEFAULT 0,
            advance       REAL    DEFAULT 0,
            filer_status  TEXT    DEFAULT "Non-Filer",
            fbr_tax       REAL    DEFAULT 0,
            pra_tax       REAL    DEFAULT 0,
            tax_paid      INTEGER DEFAULT 0,
            is_cancelled  INTEGER DEFAULT 0,
            cancel_reason TEXT    DEFAULT "",
            notes         TEXT    DEFAULT "",
            home_address  TEXT    DEFAULT "",
            created_at    TEXT    DEFAULT ""
        );

        CREATE TABLE IF NOT EXISTS audit_log (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            action     TEXT,
            booking_id INTEGER,
            details    TEXT,
            ts         TEXT DEFAULT ""
        );

        CREATE INDEX IF NOT EXISTS idx_date   ON bookings(event_date);
        CREATE INDEX IF NOT EXISTS idx_shift  ON bookings(shift);
        CREATE INDEX IF NOT EXISTS idx_cnic   ON bookings(cnic);
        CREATE INDEX IF NOT EXISTS idx_phone  ON bookings(phone);

        CREATE TABLE IF NOT EXISTS customers (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            phone            TEXT    UNIQUE,
            name             TEXT,
            cnic             TEXT    DEFAULT "",
            total_bookings   INTEGER DEFAULT 0,
            first_event_date TEXT    DEFAULT "",
            last_event_date  TEXT    DEFAULT "",
            total_spent      REAL    DEFAULT 0,
            created_at       TEXT    DEFAULT ""
        );
        """)
        self.cx.commit()

                                                                           
        for col_sql in [
            "ALTER TABLE bookings ADD COLUMN final_payment REAL DEFAULT 0",
            "ALTER TABLE bookings ADD COLUMN cleared_at    TEXT DEFAULT ''",
            "ALTER TABLE bookings ADD COLUMN home_address  TEXT DEFAULT ''",
            "ALTER TABLE bookings ADD COLUMN discount      REAL DEFAULT 0",
            "ALTER TABLE bookings ADD COLUMN surplus       REAL DEFAULT 0",
            "ALTER TABLE bookings ADD COLUMN p_fans        INTEGER DEFAULT 0",
        ]:
            try:
                self.cx.execute(col_sql)
                self.cx.commit()
            except Exception:
                pass                                       

        # ── FPH Menu table (food-per-head orders linked to bookings) ─────
        self.cx.executescript("""
        CREATE TABLE IF NOT EXISTS fph_menus (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            booking_id    INTEGER DEFAULT 0,
            customer_name TEXT    DEFAULT '',
            booking_number TEXT   DEFAULT '',
            selections    TEXT    DEFAULT '{}',
            notes         TEXT    DEFAULT '',
            created_at    TEXT    DEFAULT (datetime('now','localtime'))
        );
        CREATE INDEX IF NOT EXISTS idx_fph_booking ON fph_menus(booking_id);
        """)
        self.cx.commit()

                                                                      
    def _log(self, action, bid, detail):
        ts = datetime.datetime.now().strftime("%d-%b-%Y %I:%M %p")
        self.cx.execute(
            "INSERT INTO audit_log(action,booking_id,details,ts) VALUES(?,?,?,?)",
            (action, bid, detail, ts))
        self.cx.commit()

    @staticmethod
    def _calc(persons, rate, advance, filer):
        p, r, a = int(persons or 0), float(rate or 0), float(advance or 0)
        total   = p * r
        pra     = round(total * 0.05, 2)
        fbr     = round(total * (0.10 if filer == "Filer" else 0.20), 2)
        rem     = total - a
        return total, rem, pra, fbr

                                                                      
    def availability(self, date: str):
        rows = self.cx.execute(
            "SELECT shift FROM bookings WHERE event_date=? AND is_cancelled=0",
            (date,)).fetchall()
        taken = {r["shift"] for r in rows}
        return {
            "taken":  list(taken),   # list, not set — must be JSON-serializable
            "count":  len(taken),
            "full":   len(taken) >= 4,
            "open":   len(taken) == 0,
        }

    def month_avail(self, year, month):
        prefix = f"{year}-{month:02d}-"
        rows = self.cx.execute(
            "SELECT event_date, shift FROM bookings WHERE event_date LIKE ? AND is_cancelled=0",
            (prefix + "%",)).fetchall()
        raw = {}
        for r in rows:
            day = int(r["event_date"][8:])
            raw.setdefault(day, set()).add(r["shift"])
        # Convert sets → lists so result is JSON-serializable
        return {day: list(shifts) for day, shifts in raw.items()}

                                                                      
    def add(self, d: dict):
        av = self.availability(d["event_date"])
        if d["shift"] in av["taken"]:
            return None, f"❌ {d['shift']} shift already booked for {d['event_date']}"
        if av["full"]:
            return None, f"❌ All 4 shifts are booked for {d['event_date']}"

        total, rem, pra, fbr = self._calc(
            d.get("persons", 0), d.get("rate", 0),
            d.get("advance", 0), d.get("filer_status", "Non-Filer"))

        bt = datetime.datetime.now().strftime("%d-%b-%Y %I:%M %p")
        cur = self.cx.execute("""
            INSERT INTO bookings
              (customer_name,cnic,phone,booking_time,event_date,shift,
               persons,menu_type,event_type,rate,advance,
               filer_status,fbr_tax,pra_tax,notes,home_address,p_fans)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (d["customer_name"], d.get("cnic",""), d.get("phone",""),
              bt, d["event_date"], d["shift"],
              int(d.get("persons",0)), d.get("menu_type","FPH"),
              d.get("event_type","Mehndi"), float(d.get("rate",0)),
              float(d.get("advance",0)), d.get("filer_status","Non-Filer"),
              fbr, pra, d.get("notes",""), d.get("home_address",""),
              int(d.get("p_fans", 0))))
        self.cx.commit()
        bid = cur.lastrowid
        self.upsert_customer(
            d["customer_name"], d.get("phone",""), d.get("cnic",""),
            d["event_date"], total)
        return bid, f"✅ Booking #{bid} confirmed for {d['customer_name']}!"

    def update(self, bid: int, d: dict):
        total, rem, pra, fbr = self._calc(
            d.get("persons",0), d.get("rate",0),
            d.get("advance",0), d.get("filer_status","Non-Filer"))
        self.cx.execute("""
            UPDATE bookings SET
              customer_name=?, cnic=?, phone=?, event_date=?, shift=?,
              persons=?, menu_type=?, event_type=?, rate=?, advance=?,
              filer_status=?, fbr_tax=?, pra_tax=?, notes=?, home_address=?,
              p_fans=?
            WHERE id=?
        """, (d["customer_name"], d.get("cnic",""), d.get("phone",""),
              d["event_date"], d["shift"],
              int(d.get("persons",0)), d.get("menu_type","FPH"),
              d.get("event_type","Mehndi"), float(d.get("rate",0)),
              float(d.get("advance",0)), d.get("filer_status","Non-Filer"),
              fbr, pra, d.get("notes",""), d.get("home_address",""),
              int(d.get("p_fans", 0)), bid))
        self.cx.commit()
        self._log("EDIT", bid, f"Updated by operator")
        return True

    def cancel(self, bid: int, reason: str = ""):
        self.cx.execute(
            "UPDATE bookings SET is_cancelled=1, cancel_reason=? WHERE id=?",
            (reason, bid))
        self.cx.commit()
        self._log("CANCEL", bid, reason)

    def reset_to_pending(self, bid: int):
        """
        Undo a cleared or cancelled status — reset the booking back to PENDING.
        Clears: tax_paid, final_payment, cleared_at, discount, surplus, is_cancelled, cancel_reason.
        """
        self.cx.execute("""
            UPDATE bookings SET
              is_cancelled=0, cancel_reason='',
              tax_paid=0, final_payment=0, cleared_at='',
              discount=0, surplus=0
            WHERE id=?
        """, (bid,))
        self.cx.commit()
        self._log("RESET_PENDING", bid, "Status reset to Pending by operator")

    def mark_cleared(self, bid: int, final_payment: float, discount: float = 0.0, surplus: float = 0.0):
        """Record final payment, optional discount, and optional surplus charge.
        Net payable = gross_total - discount + surplus.
        """
        cleared_at = datetime.datetime.now().strftime("%d-%b-%Y %I:%M %p")
        self.cx.execute(
            "UPDATE bookings SET tax_paid=1, final_payment=?, cleared_at=?, discount=?, surplus=? WHERE id=?",
            (final_payment, cleared_at, discount, surplus, bid))
        self.cx.commit()
        self._log("CLEARED", bid, f"Final payment Rs.{final_payment:,.0f}, Discount Rs.{discount:,.0f}, Surplus Rs.{surplus:,.0f} on {cleared_at}")
        return cleared_at

    def get(self, bid: int):
        r = self.cx.execute(
            "SELECT * FROM bookings WHERE id=?", (bid,)).fetchone()
        return dict(r) if r else None

    def search(self, q: str, include_cancelled=False):
        like = f"%{q}%"
        cancel_clause = "" if include_cancelled else "AND is_cancelled=0"
        rows = self.cx.execute(f"""
            SELECT * FROM bookings
            WHERE (customer_name LIKE ? OR cnic LIKE ? OR phone LIKE ?
                   OR CAST(id AS TEXT)=? OR event_date LIKE ? OR event_type LIKE ?)
              {cancel_clause}
            ORDER BY event_date DESC LIMIT 200
        """, (like, like, like, q, like, like)).fetchall()
        return [dict(r) for r in rows]

    def recent(self, n=30):
        rows = self.cx.execute(
            "SELECT * FROM bookings WHERE is_cancelled=0 ORDER BY id DESC LIMIT ?",
            (n,)).fetchall()
        return [dict(r) for r in rows]

    def get_cancelled_bookings(self) -> list:
        """Return all cancelled/deleted bookings for the history log."""
        rows = self.cx.execute(
            "SELECT * FROM bookings WHERE is_cancelled=1 ORDER BY id DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    def save_fph_menu(self, data: dict) -> dict:
        """Save a Food-Per-Head menu selection linked to a booking."""
        import json as _json
        ts = __import__('datetime').datetime.now().strftime("%d-%b-%Y %I:%M %p")
        cur = self.cx.execute(
            "INSERT INTO fph_menus "
            "(booking_id, customer_name, booking_number, selections, notes, created_at) "
            "VALUES (?,?,?,?,?,?)",
            (
                data.get("booking_id", 0),
                data.get("customer_name", ""),
                data.get("booking_number", ""),
                _json.dumps(data.get("selections", {}), ensure_ascii=False),
                data.get("notes", ""),
                ts,
            ),
        )
        self.cx.commit()
        return {"success": True, "id": cur.lastrowid}

    def get_fph_menus(self) -> list:
        """Return all saved FPH menu records, newest first."""
        rows = self.cx.execute(
            "SELECT * FROM fph_menus ORDER BY created_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    def get_fph_menu_by_booking(self, booking_id: int):
        """Return the most recent FPH menu for a given booking id."""
        row = self.cx.execute(
            "SELECT * FROM fph_menus WHERE booking_id=? ORDER BY created_at DESC LIMIT 1",
            (booking_id,),
        ).fetchone()
        return dict(row) if row else None

    def delete_fph_menu(self, menu_id: int) -> dict:
        """Hard-delete a single FPH menu row by id."""
        cur = self.cx.execute(
            "DELETE FROM fph_menus WHERE id=?", (menu_id,)
        )
        self.cx.commit()
        return {"success": cur.rowcount > 0, "deleted": cur.rowcount}

    def upcoming(self):
        today = datetime.date.today().isoformat()
        rows = self.cx.execute(
            "SELECT * FROM bookings WHERE event_date>=? AND is_cancelled=0 ORDER BY event_date",
            (today,)).fetchall()
        return [dict(r) for r in rows]

                                                                      
    def monthly_report(self, year, month):
        prefix = f"{year}-{month:02d}-"
        rows = self.cx.execute(
            "SELECT * FROM bookings WHERE event_date LIKE ? AND is_cancelled=0",
            (prefix+"%",)).fetchall()
        return [dict(r) for r in rows]

    def summary(self, year, month):
        rows = self.monthly_report(year, month)
        total_rev  = sum((r["persons"] or 0) * (r["rate"] or 0) for r in rows)
        total_adv  = sum(r["advance"] or 0 for r in rows)
        total_pra  = sum(r["pra_tax"] or 0 for r in rows)
        total_fbr  = sum(r["fbr_tax"] or 0 for r in rows)
        return {
            "count":    len(rows),
            "revenue":  total_rev,
            "advance":  total_adv,
            "remaining":total_rev - total_adv,
            "pra_tax":  total_pra,
            "fbr_tax":  total_fbr,
            "bookings": rows,
        }

    def yearly_monthly(self, year):
        out = []
        for m in range(1, 13):
            s = self.summary(year, m)
            out.append({"month": MONTHS[m-1], "month_num": m, **s})
        return out

                                                                      
    def upsert_customer(self, name, phone, cnic, event_date, total):
        key = phone.strip() if phone.strip() else cnic.strip()
        if not key:
            return
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        existing = self.cx.execute(
            "SELECT id, total_bookings, first_event_date FROM customers WHERE phone=?",
            (key,)).fetchone()
        if existing:
            first = existing["first_event_date"] or event_date
            self.cx.execute("""UPDATE customers SET
                name=?, cnic=?, total_bookings=total_bookings+1,
                last_event_date=?, first_event_date=?, total_spent=total_spent+?
                WHERE phone=?""",
                (name, cnic, event_date, first, total, key))
        else:
            self.cx.execute("""INSERT INTO customers
                (phone, name, cnic, total_bookings, first_event_date, last_event_date, total_spent, created_at)
                VALUES (?,?,?,1,?,?,?,?)""",
                (key, name, cnic, event_date, event_date, total, now))
        self.cx.commit()

    def customer_history(self, phone):
        rows = self.cx.execute(
            "SELECT * FROM bookings WHERE phone=? ORDER BY event_date DESC", (phone,)).fetchall()
        return [dict(r) for r in rows]

    def all_customers(self):
        rows = self.cx.execute(
            "SELECT * FROM customers ORDER BY total_bookings DESC, last_event_date DESC").fetchall()
        return [dict(r) for r in rows]

    def search_customers(self, q):
        like = f"%{q}%"
        rows = self.cx.execute(
            "SELECT * FROM customers WHERE name LIKE ? OR phone LIKE ? OR cnic LIKE ? LIMIT 100",
            (like, like, like)).fetchall()
        return [dict(r) for r in rows]

    def backup(self, dest_dir=BACKUP_DIR):
        os.makedirs(dest_dir, exist_ok=True)
        ts  = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        dst = os.path.join(dest_dir, f"dhanak_{ts}.db")
        shutil.copy2(self.path, dst)
                                   
        files = sorted(
            [f for f in os.listdir(dest_dir) if f.endswith(".db")],
            reverse=True)
        for old in files[30:]:
            try: os.remove(os.path.join(dest_dir, old))
            except: pass
        return dst

                                                                      
                          
                                                                      

class ReceiptGen:
    """
    Generates two distinct receipt types:

    1. BOOKING RECEIPT  (thermal printer, printed at booking time)
       - Compact 42-char wide text
       - Customer copy + office copy on one roll
       - Shows advance paid, balance due, thank-you message

    2. FINAL CLEARANCE RECEIPT  (A4 inkjet/laser printer)
       - Printed when customer clears full payment before/after the event
       - Shows PAID IN FULL stamp area
       - Formal proof-of-payment document
       - Includes all tax breakdowns for PRA records
    """

    def __init__(self, cfg: Config):
        self.cfg = cfg

    @staticmethod
    def _fmt(n):
        try:    return f"Rs. {int(n):,}"
        except: return "Rs. 0"

    def _get_printer(self, key: str) -> str:
        """Return configured printer name, or empty string if not set."""
        return (self.cfg.get(key, "") or "").strip()

    @staticmethod
    def _find_sumatra() -> str:
        """
        Return absolute path to SumatraPDF.exe.
        Checks: standard install dirs, PATH, Windows registry App Paths.
        """
        username = os.environ.get("USERNAME", "") or ""
        candidates = [
            os.path.join("C:\\Program Files\\SumatraPDF", "SumatraPDF.exe"),
            os.path.join("C:\\Program Files (x86)\\SumatraPDF", "SumatraPDF.exe"),
            os.path.join("C:\\Users", username, "AppData\\Local\\SumatraPDF", "SumatraPDF.exe"),
        ]
        for p in candidates:
            if os.path.exists(p):
                return p
        import shutil
        found = shutil.which("SumatraPDF") or shutil.which("sumatrapdf")
        if found:
            return found
        if sys.platform == "win32":
            try:
                import winreg
                for root in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
                    try:
                        key = winreg.OpenKey(root,
                            r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\SumatraPDF.exe")
                        val, _ = winreg.QueryValueEx(key, "")
                        winreg.CloseKey(key)
                        if val and os.path.exists(val):
                            return val
                    except OSError:
                        pass
            except ImportError:
                pass
        return ""


    def _silent_print_html(self, html_path: str, printer_name: str,
                           delay_ms: int = 0) -> bool:
        """
        Silently send an HTML file to a named printer via SumatraPDF.
        delay_ms: wait this many milliseconds before printing (for sequential jobs).
        Returns True if attempted, False → caller should open browser dialog.
        """
        if not printer_name or sys.platform != "win32":
            return False
        sumatra = self._find_sumatra()
        if not sumatra:
            return False
        abs_path = os.path.abspath(html_path)
        def _do_print():
            if delay_ms:
                import time; time.sleep(delay_ms / 1000.0)
            try:
                subprocess.Popen([
                    sumatra, "-print-to", printer_name,
                    "-print-settings", "noscale",
                    abs_path
                ])
            except Exception:
                pass
        threading.Thread(target=_do_print, daemon=True).start()
        return True

    def _hall(self, key, default=""):
        return self.cfg.get(key, default)

    def print_both_receipts(self, b: dict, final_payment: float = 0.0,
                            cleared_at: str = "", discount: float = 0.0,
                            surplus: float = 0.0) -> dict:
        """
        One-click print: thermal booking receipt first, then (after 4 s delay)
        the A4 clearance receipt.  Both go directly to the configured printers
        via SumatraPDF — no dialogs.
        Returns {"thermal": bool, "clearance": bool, "sumatra": bool}.
        """
        import webbrowser
        os.makedirs(RECEIPTS_DIR, exist_ok=True)
        sumatra      = self._find_sumatra()
        th_printer   = self._get_printer("thermal_printer")
        a4_printer   = self._get_printer("a4_printer")
        result       = {"sumatra": bool(sumatra), "thermal": False, "clearance": False}

        # ── Thermal receipt ──────────────────────────────────────────────
        th_html = os.path.join(RECEIPTS_DIR, f"booking_receipt_{b['id']}.html")
        with open(th_html, "w", encoding="utf-8") as f:
            f.write(self.thermal_booking_html(b))
        if sumatra and th_printer:
            result["thermal"] = self._silent_print_html(th_html, th_printer, delay_ms=0)
        else:
            # fallback: open in browser
            abs_path = os.path.abspath(th_html).replace("\\", "/")
            webbrowser.open(f"file:///{abs_path}")
            result["thermal"] = True

        # ── A4 Clearance receipt (4 second delay so thermal finishes first) ─
        if not cleared_at:
            cleared_at = datetime.datetime.now().strftime("%d-%b-%Y %I:%M %p")
        cl_html = os.path.join(RECEIPTS_DIR, f"clearance_{b['id']}.html")
        with open(cl_html, "w", encoding="utf-8") as f:
            f.write(self.clearance_html(b, final_payment, cleared_at,
                                        discount=discount, surplus=surplus))
        if sumatra and a4_printer:
            result["clearance"] = self._silent_print_html(cl_html, a4_printer, delay_ms=4000)
        else:
            # fallback: open in browser after a short delay
            def _open_clearance():
                import time; time.sleep(4)
                abs_path = os.path.abspath(cl_html).replace("\\", "/")
                webbrowser.open(f"file:///{abs_path}")
            threading.Thread(target=_open_clearance, daemon=True).start()
            result["clearance"] = True

        return result

                                                                  
                                               
                                                            
                                                                  

    def thermal_booking_text(self, b: dict) -> str:
        """
        Compact 42-char thermal receipt.
        Prints CUSTOMER COPY + OFFICE COPY on one continuous roll.
        """
        W    = 42
        sep  = "-" * W
        sep2 = "=" * W
        hall = self._hall("hall_name", "Dhanak Banquet Hall")
        addr = self._hall("hall_address", "Khanewal, Pakistan")
        ph   = self._hall("hall_phone1","") + "  " + self._hall("hall_phone2","")

        total   = (b.get("persons",0) or 0) * (b.get("rate",0) or 0)
        advance = float(b.get("advance",0) or 0)
        rem     = total - advance

        def copy_block(label, show_booking_id=True):
            lines = [
                sep2,
                hall[:W].center(W),
                addr[:W].center(W),
                ph[:W].center(W),
                sep2,
                f"*** {label} ***".center(W),
                sep,
            ]
            if show_booking_id:
                lines.append(f"Booking #   : {b['id']}")
            lines += [
                f"Booked On   : {b.get('booking_time','')}",
                sep,
                "CUSTOMER DETAILS",
                f"Name        : {b.get('customer_name','')}",
                f"Phone       : {b.get('phone','')}",
                f"CNIC        : {b.get('cnic','')}",
                f"Address     : {b.get('home_address','') or '—'}",
                sep,
                "EVENT",
                f"Date        : {b.get('event_date','')}",
                f"Shift       : {b.get('shift','')} Shift",
                f"Event Type  : {b.get('event_type','')}",
                f"Menu        : {b.get('menu_type','')}",
                f"Persons     : {b.get('persons',0)}",
                sep,
                "PAYMENT SUMMARY",
                f"Rate/Head   : {self._fmt(b.get('rate',0))}",
                f"Total Bill  : {self._fmt(total)}",
                f"Advance Pd  : {self._fmt(advance)}",
                f"Balance Due : {self._fmt(rem)}",
                sep,
                "Thank you for choosing".center(W),
                hall[:W].center(W),
                "We look forward to serving you!".center(W),
                sep2,
                "",
            ]
            return lines

        W = 42
        cut_line = [
            "",
            "-" * W,
            "✂  TEAR HERE  ✂".center(W),
            "-" * W,
            "",
        ]
        lines  = copy_block("CUSTOMER COPY", show_booking_id=False)
        lines += cut_line
        lines += copy_block("OFFICE COPY",  show_booking_id=True)
        return "\n".join(lines)

                                              
    def thermal_text(self, b: dict) -> str:
        return self.thermal_booking_text(b)

    # ─────────────────────────────────────────────────────────
    # HTML RECEIPTS — opens in browser, uses browser print dialog
    # Fixes: no more Notepad glitch, proper thermal/A4 paper sizing
    # ─────────────────────────────────────────────────────────

    def _thermal_css(self) -> str:
        """
        80mm thermal CSS — pushed to maximum usable width.
        body fills full 80mm with just 0.5mm side padding for clean edges.
        Qt headless + SumatraPDF handle actual printer margins.
        """
        return (
            "@page{size:80mm auto;margin:0;}"
            "*{box-sizing:border-box;margin:0;padding:0;}"
            "html{width:80mm;margin:0;padding:0;}"
            "body{font-family:'Times New Roman',Times,serif;font-size:19px;"
            "font-weight:800;color:#000000;background:#fff;"
            "max-width:80mm;width:80mm;margin:0;padding:0 0.5mm;overflow:hidden;"
            "-webkit-print-color-adjust:exact;print-color-adjust:exact;"
            "-webkit-text-stroke:0.6px #000000;text-rendering:geometricPrecision;}"
            "td,div,span{color:#000000;font-weight:800;-webkit-text-stroke:0.6px #000000;}"
            ".c{text-align:center;}"
            ".sep{border:none;border-top:2px solid #000;margin:6px 0;}"
            ".sep-dashed{border:none;border-top:1px dashed #000;margin:5px 0;}"
            ".eq{text-align:center;font-size:18px;font-weight:800;letter-spacing:2px;margin:4px 0;}"
            ".eq-header{max-width:100%;margin-left:auto;margin-right:auto;}"
            "table{width:100%;border-collapse:collapse;table-layout:fixed;}"
            "td{font-size:19px;font-weight:800;color:#000000;padding:5px 0;"
            "overflow:hidden;word-wrap:break-word;word-break:break-word;}"
            "td.lbl{width:35%;}"
            "td.val{text-align:right;}"
            ".sec{text-align:center;font-size:18px;font-weight:800;letter-spacing:1px;margin:5px 0 4px;}"
            ".footer{text-align:center;font-size:17px;font-weight:800;margin-top:8px;}"
        )

    def _thermal_header(self) -> str:
        """
        Thermal receipt header — styled DBH monogram + hall name + address.
        Uses Georgia italic for the monogram letters only (not an image,
        so it always prints and never gets cut off on any thermal printer).
        """
        hall = self._hall("hall_name",    "Dhanak Banquet Hall")
        addr = self._hall("hall_address", "Khanewal, Pakistan")
        ph1  = self._hall("hall_phone1",  "")
        ph2  = self._hall("hall_phone2",  "")
        eq   = "================"
        # Styled text monogram — Georgia italic, size-varied letters for depth.
        # No negative letter-spacing on first/last chars (avoids left/right clip in print/PDF).
        monogram = (
            "<div class='c' style='margin:4px 0 2px;line-height:1;'>"
            "<span style='font-family:Georgia,serif;font-size:54px;"
                         "font-style:italic;font-weight:800;'>D</span>"
            "<span style='font-family:Georgia,serif;font-size:44px;"
                         "font-style:italic;font-weight:800;letter-spacing:-1px;'>B</span>"
            "<span style='font-family:Georgia,serif;font-size:54px;"
                         "font-style:italic;font-weight:800;'>H</span>"
            "</div>"
            # thin swash line beneath the letters
            "<div class='c' style='font-family:Georgia,serif;font-style:italic;"
                             "font-size:14px;letter-spacing:6px;margin:-2px 0 4px;"
                             ">&#x2015;&#x2015;&#x2015;&#x2015;&#x2015;&#x2015;</div>"
        )
        return (
            monogram
            + f"<div class='eq eq-header'>{eq}</div>"
            + f"<div class='c' style='font-size:22px;font-weight:800;margin:5px 0;'>{hall}</div>"
            + f"<div class='c' style='font-size:18px;font-weight:800;'>{addr}</div>"
            + f"<div class='c' style='font-size:18px;font-weight:800;'>{ph1}&nbsp;&nbsp;{ph2}</div>"
            + f"<div class='eq eq-header'>{eq}</div>"
        )

    def _trow(self, label: str, value: str) -> str:
        """One label : value row — both pure black bold."""
        return (
            f"<tr>"
            f"<td class='lbl'>{label}</td>"
            f"<td class='val'>{value}</td>"
            f"</tr>"
        )

    def thermal_customer_html(self, b: dict) -> str:
        """
        Customer Copy — 80mm thermal HTML.
        Identical detail to office copy (minus booking #).
        Decorated with floral Unicode borders for a premium feel.
        """
        hall    = self._hall("hall_name", "Dhanak Banquet Hall")
        total   = (b.get("persons", 0) or 0) * (b.get("rate", 0) or 0)
        advance = float(b.get("advance", 0) or 0)
        rem     = total - advance

        # ── decorative elements ──────────────────────────────────────────
        # Flower row — Unicode blooms that every thermal printer can render
        flower  = "<div class='flw'>&#x2741;&nbsp;&#x273F;&nbsp;&#x2741;&nbsp;&#x273F;&nbsp;&#x2741;&nbsp;&#x273F;&nbsp;&#x2741;&nbsp;&#x273F;&nbsp;&#x2741;</div>"
        # Vine separator — lighter decorative line between sections
        vine    = "<div class='vin'>- &#x2741; - &#x273F; - &#x2741; - &#x273F; - &#x2741; -</div>"

        # ── data rows ───────────────────────────────────────────────────
        cust_rows = (
            self._trow("Booked On", b.get("booking_time", "") or "—")
            + self._trow("Name",      b.get("customer_name", "") or "—")
            + self._trow("Phone",     b.get("phone", "") or "—")
            + self._trow("CNIC",      b.get("cnic", "") or "—")
            + self._trow("Address",   b.get("home_address", "") or "—")
        )
        event_rows = (
            self._trow("Date",      b.get("event_date", ""))
            + self._trow("Shift",   b.get("shift", ""))
            + self._trow("Event",   b.get("event_type", "") or "—")
            + self._trow("Menu",    b.get("menu_type", "") or "—")
            + self._trow("Persons", str(b.get("persons", 0)))
            + self._trow("Rate/Head", self._fmt(b.get("rate", 0)))
        )
        pay_rows = (
            self._trow("Total Bill", self._fmt(total))
            + self._trow("Advance",  self._fmt(advance))
            + self._trow("Balance",  self._fmt(rem))
        )

        # P.Fans (only if > 0)
        p_fans = int(b.get("p_fans", 0) or 0)
        fans_html = ""
        if p_fans > 0:
            fan_charge = p_fans * 200
            fans_html = "<table>" + self._trow("P.Fans", f"{p_fans} x Rs.200 = {self._fmt(fan_charge)}") + "</table>"
        tax_labels = (
            "<div class='sec' style='font-size:15px;margin:4px 0 2px;'>Withholding Tax 10%</div>"
            "<div class='sec' style='font-size:15px;margin:2px 0 4px;'>PRA Tax 5%</div>"
        )

        # ── extra CSS for floral decorations ────────────────────────────
        extra_css = (
            ".flw{text-align:center;font-size:22px;font-weight:800;margin:7px 0;letter-spacing:4px;}"
            ".vin{text-align:center;font-size:19px;font-weight:800;margin:6px 0;letter-spacing:3px;}"
            ".copy-label{text-align:center;font-size:21px;font-weight:800;letter-spacing:3px;"
                        "border-top:2px solid #000;border-bottom:2px solid #000;"
                        "padding:6px 0;margin:6px 0;}"
        )

        return (
            "<!DOCTYPE html><html><head><meta charset='UTF-8'>"
            f"<style>{self._thermal_css()}{extra_css}</style>"
            "</head><body>"
            + flower
            + self._thermal_header()
            + flower
            + "<div class='copy-label'>✦ CUSTOMER COPY ✦</div>"
            + vine
            + "<div class='sec'>— CUSTOMER DETAILS —</div>"
            + f"<table>{cust_rows}</table>"
            + vine
            + "<div class='sec'>— EVENT DETAILS —</div>"
            + f"<table>{event_rows}</table>"
            + vine
            + "<div class='sec'>— PAYMENT —</div>"
            + f"<table>{pay_rows}</table>"
            + fans_html
            + tax_labels
            + flower
            + f"<div class='footer'>Thank you for choosing {hall}!</div>"
            + "<div class='footer' style='font-size:15px;font-weight:800;'>We look forward to serving you &#x2741;</div>"
            + flower
            + "</body></html>"
        )

    def thermal_office_html(self, b: dict) -> str:
        """
        Office Copy — 80mm thermal HTML.
        Full details including CNIC, event type, menu, and tax breakdown.
        Auto-prints on open.
        """
        hall    = self._hall("hall_name", "Dhanak Banquet Hall")
        total   = (b.get("persons", 0) or 0) * (b.get("rate", 0) or 0)
        advance = float(b.get("advance", 0) or 0)
        rem     = total - advance

        cust_rows = (
            self._trow("Booking #",   f"#{b['id']}")
            + self._trow("Booked On", b.get("booking_time", "") or "—")
            + self._trow("Name",      b.get("customer_name", "") or "—")
            + self._trow("Phone",     b.get("phone", "") or "—")
            + self._trow("CNIC",      b.get("cnic", "") or "—")
            + self._trow("Address",   b.get("home_address", "") or "—")
        )
        event_rows = (
            self._trow("Date",       b.get("event_date", ""))
            + self._trow("Shift",    b.get("shift", ""))
            + self._trow("Event",    b.get("event_type", "") or "—")
            + self._trow("Menu",     b.get("menu_type", "") or "—")
            + self._trow("Persons",  str(b.get("persons", 0)))
            + self._trow("Rate/Head",self._fmt(b.get("rate", 0)))
        )
        pay_rows = (
            self._trow("Total Bill", self._fmt(total))
            + self._trow("Advance",  self._fmt(advance))
            + self._trow("Balance",  self._fmt(rem))
        )

        # P.Fans (only if > 0) — office copy
        pf_o = int(b.get("p_fans", 0) or 0)
        fans_o = ""
        if pf_o > 0:
            fans_o = "<table>" + self._trow("P.Fans", f"{pf_o} x Rs.200 = {self._fmt(pf_o*200)}") + "</table>"
        tax_o = (
            "<div class='sec' style='font-size:15px;margin:4px 0 2px;'>Withholding Tax 10%</div>"
            "<div class='sec' style='font-size:15px;margin:2px 0 4px;'>PRA Tax 5%</div>"
        )

        return (
            "<!DOCTYPE html><html><head><meta charset='UTF-8'>"
            f"<style>{self._thermal_css()}</style>"
            "</head><body>"
            + self._thermal_header()
            + "<div class='eq eq-header'>================</div>"
            + "<div class='c' style='font-size:18px;font-weight:800;letter-spacing:2px;'>** OFFICE COPY **</div>"
            + "<div class='eq eq-header'>================</div>"
            + f"<table>{cust_rows}</table>"
            + "<hr class='sep-dashed'>"
            + "<div class='sec'>- EVENT -</div>"
            + f"<table>{event_rows}</table>"
            + "<hr class='sep-dashed'>"
            + "<div class='sec'>- PAYMENT -</div>"
            + f"<table>{pay_rows}</table>"
            + fans_o + tax_o
            + "<div class='eq eq-header'>================</div>"
            + f"<div class='footer'>Thank you for choosing {hall}!</div>"
            + "<div class='eq eq-header'>================</div>"
            + "</body></html>"
        )

    # Keep old method name as alias so existing callers don't break
    def thermal_booking_html(self, b: dict) -> str:
        return self.thermal_customer_html(b)

    def clearance_html(self, b: dict, final_payment: float, cleared_at: str, discount: float = 0.0, surplus: float = 0.0) -> str:
        """
        A4 formal clearance receipt — printed only when a booking is physically
        cleared.  Includes decorative floral border, celebratory quotes, and a
        full payment breakdown.  Opens in browser so the user can use the
        browser print dialog (Ctrl+P → A4 paper).
        """
        import datetime as _dt
        hall  = self._hall("hall_name",    "Dhanak Banquet Hall")
        addr  = self._hall("hall_address", "Khanewal, Pakistan")
        ph1   = self._hall("hall_phone1",  "")
        ph2   = self._hall("hall_phone2",  "")
        gross_total   = (b.get("persons", 0) or 0) * (b.get("rate", 0) or 0)
        discount      = float(discount or 0)
        surplus       = float(b.get("surplus", 0) or 0)
        disc_pct      = round((discount / gross_total * 100), 2) if gross_total > 0 else 0
        net_total     = max(0.0, gross_total - discount + surplus)
        adv           = float(b.get("advance", 0) or 0)
        total_recv    = adv + final_payment
        balance       = max(0.0, net_total - total_recv)
        ts            = cleared_at or _dt.datetime.now().strftime("%d-%b-%Y %I:%M %p")

        # ── decorative quotes (wine quote excluded — not printed) ─────────
        quotes = [
            "Marriages are made in heaven, celebrated on earth.",
            "May your union bloom like a garden in full spring.",
            "Every love story is beautiful, but yours is our favourite.",
        ]
        import random
        quote = random.choice(quotes)

        # ── CSS ──────────────────────────────────────────────────────────
        css = """
@page { size: A4; margin: 10mm 8mm 10mm 8mm; }
* { box-sizing: border-box; margin: 0; padding: 0; }
html, body { height: 100%; }
body {
    font-family: 'Georgia', serif;
    font-size: 13.5px;
    font-weight: bold;
    color: #000;
    background: #fff;
    -webkit-print-color-adjust: exact;
    print-color-adjust: exact;
    max-width: 210mm;
    margin: 0 auto;
    padding: 0;
    height: 100%;
    display: flex;
    flex-direction: column;
}
.page-frame {
    border: 5px double #8B1A1A;
    outline: 1.5px solid #C8A951;
    outline-offset: -8px;
    padding: 14px 22px 14px;
    position: relative;
    flex: 1;
    display: flex;
    flex-direction: column;
    min-height: calc(297mm - 20mm);
}
.corner { position: absolute; font-size: 18px; line-height:1; color: #8B1A1A; }
.corner.tl { top: 4px;  left: 6px; }
.corner.tr { top: 4px;  right: 6px; }
.corner.bl { bottom: 4px; left: 6px; }
.corner.br { bottom: 4px; right: 6px; }
.vine-top {
    text-align: center;
    font-size: 13px;
    color: #8B1A1A;
    letter-spacing: 3px;
    margin: 2px 0 5px;
}
.logo-wrap { text-align: center; margin: 3px 0 3px; }
.logo-wrap img { width: 64px; height: auto; display: inline-block; }
.hall-name {
    text-align: center;
    font-size: 19px;
    font-weight: bold;
    letter-spacing: 2px;
    color: #8B1A1A;
    text-transform: uppercase;
    margin: 2px 0;
}
.hall-sub {
    text-align: center;
    font-size: 12px;
    font-weight: bold;
    color: #333;
    margin-top: 1px;
}
.doc-title {
    text-align: center;
    font-size: 14px;
    font-weight: bold;
    letter-spacing: 2px;
    text-transform: uppercase;
    border-top: 2px solid #8B1A1A;
    border-bottom: 2px solid #8B1A1A;
    padding: 4px 0;
    margin: 6px 0 4px;
    color: #8B1A1A;
}
.booking-ref {
    text-align: center;
    font-size: 12px;
    font-weight: bold;
    color: #333;
    margin-bottom: 5px;
}
.detail-grid {
    width: 100%;
    border-collapse: collapse;
    margin-bottom: 5px;
}
.detail-grid td {
    padding: 3.5px 8px;
    font-size: 13px;
    font-weight: bold;
    border-bottom: 1.5px solid #888;
    vertical-align: top;
}
.detail-grid .lbl {
    color: #000;
    font-weight: bold;
    width: 38%;
    white-space: nowrap;
}
.detail-grid .val {
    font-weight: bold;
    color: #000;
    text-align: right;
}
.section-hdr td {
    background: #d0c0a0;
    color: #000;
    font-weight: bold;
    font-size: 11px;
    letter-spacing: 1px;
    text-transform: uppercase;
    padding: 3px 8px;
    border-top: 2px solid #555;
    border-bottom: 2px solid #555;
}
.stamp-wrap { text-align: center; margin: 7px 0 5px; }
.stamp {
    display: inline-block;
    border: 3.5px solid #000;
    border-radius: 4px;
    padding: 5px 24px;
    color: #000;
    font-size: 16px;
    font-weight: bold;
    letter-spacing: 3px;
    text-transform: uppercase;
    transform: rotate(-1.5deg);
}
.quote-band {
    text-align: center;
    font-style: italic;
    font-size: 12px;
    font-weight: bold;
    color: #000;
    border-top: 2px solid #333;
    border-bottom: 2px solid #333;
    padding: 4px 16px;
    margin: 5px 0;
    line-height: 1.4;
}
.flower-row {
    text-align: center;
    font-size: 14px;
    letter-spacing: 4px;
    color: #8B1A1A;
    margin: 3px 0;
}
.sig-line {
    margin-top: 12px;
    font-size: 12px;
    font-weight: bold;
    color: #222;
    text-align: center;
}
.sig-line .sig-underlines { display: flex; justify-content: center; gap: 2em; margin-bottom: 5px; }
.sig-line .sig-underlines span { display: inline-block; width: 140px; border-bottom: 2px solid #222; }
.sig-line .sig-labels { display: flex; justify-content: center; gap: 2em; margin-top: 3px; }
.sig-line .sig-labels span { font-weight: bold; width: 140px; text-align: center; font-size: 10.5px; color: #333; }
.sig-spacer { flex: 1; }
.footer {
    text-align: center;
    font-size: 10px;
    font-weight: bold;
    color: #555;
    margin-top: 10px;
    border-top: 1px dashed #bbb;
    padding-top: 4px;
}
"""

        # ── build detail rows ────────────────────────────────────────────
        def row(lbl, val):
            return (f"<tr>"
                    f"<td class='lbl'>{lbl}</td>"
                    f"<td class='val'>{val}</td>"
                    f"</tr>")

        def shdr(title):
            return f"<tr class='section-hdr'><td colspan='2'>{title}</td></tr>"

        customer_rows = (
            shdr("Customer Details")
            + row("Booked On",    b.get("booking_time", "") or "—")
            + row("Full Name",    b.get("customer_name", "") or "—")
            + row("Phone",        b.get("phone", "") or "—")
            + row("CNIC",         b.get("cnic", "") or "—")
            + row("Home Address", b.get("home_address", "") or "—")
        )
        event_rows = (
            shdr("Event Details")
            + row("Event Date",   b.get("event_date", ""))
            + row("Shift",        b.get("shift", ""))
            + row("Event Type",   b.get("event_type", "") or "—")
            + row("Menu",         b.get("menu_type", "") or "—")
            + row("Persons",      str(b.get("persons", 0)))
            + row("Rate / Head",  self._fmt(b.get("rate", 0)))
        )
        # P.Fans (only if > 0)
        p_fans_cl = int(b.get("p_fans", 0) or 0)
        fans_cl_row = ""
        if p_fans_cl > 0:
            fc_cl = p_fans_cl * 200
            fans_cl_row = row("Pedestal Fans", f"{p_fans_cl} × Rs. 200 = {self._fmt(fc_cl)}")

        disc_str = self._fmt(discount) if discount > 0 else "None"
        payment_rows = (
            shdr("Payment Breakdown")
            + row("Gross Total Bill",           self._fmt(gross_total))
            + (row("Discount Applied",          disc_str) if discount > 0 else "")
            + (row("Surplus Charge (Seating)",  self._fmt(surplus)) if surplus > 0 else "")
            + fans_cl_row
            + (row("Net Payable",               self._fmt(net_total)) if (discount > 0 or surplus > 0) else "")
            + row("Advance Paid",               self._fmt(adv))
            + row("Final Payment",              self._fmt(final_payment))
            + row("Total Received",             self._fmt(total_recv))
            + row("Outstanding",                self._fmt(balance))
            + row("Withholding Tax",            "10%")
            + row("PRA Tax",                    "5%")
        )

        all_rows = customer_rows + event_rows + payment_rows

        return (
            "<!DOCTYPE html><html><head><meta charset='UTF-8'>"
            f"<style>{css}</style>"
            "</head><body>"

            "<div class='page-frame'>"
            "<span class='corner tl'>❀</span>"
            "<span class='corner tr'>❀</span>"
            "<span class='corner bl'>❀</span>"
            "<span class='corner br'>❀</span>"

            "<div class='vine-top'>✿ ❦ ✾ ❧ ✿ ❦ ✾ ❧ ✿ ❦ ✾ ❧ ✿</div>"

            "<div class='logo-wrap'>"
            "<img src='data:image/jpeg;base64,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' "
            "style='width:90px;height:auto;display:inline-block;' alt='DBH'/></div>"
            f"<div class='hall-name'>{hall}</div>"
            f"<div class='hall-sub'>{addr}</div>"
            f"<div class='hall-sub'>{ph1}&nbsp;&nbsp;{ph2}</div>"

            "<div class='doc-title'>Final Clearance Receipt</div>"
            f"<div class='booking-ref'>Cleared On:&nbsp;<b>{ts}</b></div>"

            "<div class='stamp-wrap'>"
            "<div class='stamp'>✔ PAID IN FULL</div>"
            "</div>"

            f"<table class='detail-grid'>{all_rows}</table>"

            "<div class='flower-row'>❀ ✿ ❀ ✿ ❀ ✿ ❀</div>"
            f"<div class='quote-band'>\"{quote}\"</div>"
            "<div class='flower-row'>❀ ✿ ❀ ✿ ❀ ✿ ❀</div>"

            "<div class='sig-spacer'></div>"

            "<div class='sig-line'>"
            "<div class='sig-underlines'>"
            "<span>&nbsp;</span><span>&nbsp;</span><span>&nbsp;</span>"
            "</div>"
            "<div class='sig-labels'>"
            "<span>Authorized by</span> <span>Customer Signature</span> <span>Official Seal</span>"
            "</div>"
            "</div>"

            f"<div class='footer'>"
            f"This is an official payment clearance document issued by {hall} · {addr}<br>"
            f"Printed on {_dt.datetime.now().strftime('%d-%b-%Y %I:%M %p')}"
            f"</div>"

            "<div class='vine-top'>✿ ❦ ✾ ❧ ✿ ❦ ✾ ❧ ✿ ❦ ✾ ❧ ✿</div>"

            "</div>"  # page-frame
            "</body></html>"
        )


    def fph_menu_html(self, menu: dict) -> str:
        """
        Generate a printable A4 FPH menu sheet — mirrors the clearance receipt style.
        menu keys: booking_id, customer_name, booking_number, selections (dict), notes, created_at
        """
        import json as _json
        import datetime as _dt

        hall  = self._hall("hall_name",    "Dhanak Banquet Hall")
        addr  = self._hall("hall_address", "Khanewal, Pakistan")
        ph1   = self._hall("hall_phone1",  "")
        ph2   = self._hall("hall_phone2",  "")

        selections = menu.get("selections", {})
        if isinstance(selections, str):
            try:   selections = _json.loads(selections)
            except: selections = {}

        cname   = menu.get("customer_name", "—")
        bnum    = menu.get("booking_number", "—")
        notes   = menu.get("notes", "")
        created = menu.get("created_at", _dt.datetime.now().strftime("%d-%b-%Y %I:%M %p"))

        # ── category definitions (matching the JS radio form) ──────────────
        CATEGORIES = [
            ("1 – Salan (Curry)", [
                "Mutton Qorma Red", "Mutton Qorma White",
                "Beef Qorma Red", "Beef Qorma White",
                "Chicken Qorma Red", "Chicken Qorma White",
            ]),
            ("2 – Namkin Chawal (Rice)", ["Mutton Biryani", "Beef Biryani", "Chicken Biryani", "Fried Rice", "Murgh Pulao", "Kabli Palao"]),
            ("3 – Sweet Dish", ["Matanajan", "Zarda", "Kheer", "Fruit Trifle", "Ice Cream Simple", "Ice Cream Walls", "Lab-e-Shirin"]),
            ("4 – Salad", ["Fresh Sabzi Salad", "Kachumber Salad", "Russian Salad", "Chanay", "Lobia", "Macaroni"]),
            ("5 – Drinks", [
                "Coke 1.5L", "Coke 1L", "Sprite 1.5L", "Sprite 1L",
                "7UP 1.5L", "7UP 1L", "Nestle Juice Regular", "Fresh Juice",
                "Tin", "NR",
            ]),
            ("6 – Raita", ["Podina Raita", "Zeera Raita", "Sada Dahi Raita"]),
            ("7 – Roti (Bread)", ["Tandoori Roti", "Khameeri Roti", "Sada Naan", "Roghni Naan", "Milky Naan", "Sheermal"]),
            ("8 – Paani (Water)", ["Sada Thanda Paani", "Branded Mineral Water", "Normal Mineral Water"]),
            ("9 – BBQ", ["Chicken Tikka Boti", "Beef Kabab", "Chicken Kabab", "Seekhi Kabab", "Malai Boti", "Reshmi Kabab"]),
            ("10 – Roast", ["Chicken Steam Roast", "Beef Steam Roast", "Chicken Brost", "Chicken Pakoda", "Chicken Candy", "Chicken Butterfly"]),
            ("11 – Fish Counter", ["Finger Fish", "Normal Fish"]),
            ("12 – Other Items", []),
        ]

        css = """
@page { size: A4; margin: 10mm 8mm 10mm 8mm; }
* { box-sizing: border-box; margin: 0; padding: 0; }
html, body { height: 100%; }
body {
    font-family: 'Georgia', serif;
    font-size: 13px;
    color: #000;
    background: #fff;
    -webkit-print-color-adjust: exact;
    print-color-adjust: exact;
    max-width: 210mm;
    margin: 0 auto;
    padding: 0;
    height: 100%;
    display: flex;
    flex-direction: column;
    font-weight: bold;
}
.page-frame {
    border: 5px double #8B1A1A;
    outline: 1.5px solid #C8A951;
    outline-offset: -8px;
    padding: 14px 22px 14px;
    position: relative;
    flex: 1;
    display: flex;
    flex-direction: column;
    min-height: calc(297mm - 20mm);
}
.corner { position: absolute; font-size: 18px; line-height:1; color: #8B1A1A; }
.corner.tl { top: 4px; left: 6px; }
.corner.tr { top: 4px; right: 6px; }
.corner.bl { bottom: 4px; left: 6px; }
.corner.br { bottom: 4px; right: 6px; }
.vine-top { text-align:center; font-size:13px; color:#8B1A1A; letter-spacing:3px; margin:2px 0 5px; }
.logo-wrap { text-align:center; margin:3px 0; }
.logo-wrap img { width:60px; height:auto; display:inline-block; }
.hall-name { text-align:center; font-size:20px; font-weight:900; letter-spacing:2px; color:#8B1A1A; text-transform:uppercase; margin:2px 0; }
.hall-sub { text-align:center; font-size:11.5px; color:#000; font-weight:bold; margin-top:1px; }
.doc-title { text-align:center; font-size:16px; font-weight:900; letter-spacing:2px; text-transform:uppercase;
    border-top:2.5px solid #8B1A1A; border-bottom:2.5px solid #8B1A1A; padding:5px 0; margin:8px 0 5px; color:#8B1A1A; }
.booking-ref { text-align:center; font-size:12px; font-weight:900; color:#000; margin-bottom:8px; }
.menu-grid { display:grid; grid-template-columns:1fr 1fr 1fr; gap:6px; margin-top:8px; }
.menu-box { border:3px solid #8B1A1A; border-radius:4px; padding:6px 8px; background:#fffdf8; font-weight:900; }
.menu-box-title { font-size:11px; font-weight:900; color:#8B1A1A; text-transform:uppercase;
    border-bottom:2.5px solid #c8a060; margin-bottom:4px; padding-bottom:2px; letter-spacing:0.3px; }
.menu-item { display:flex; align-items:flex-start; gap:5px; margin:3px 0; font-size:11px; font-weight:900; color:#000; }
.menu-item.selected { font-weight:900; color:#000; }
.menu-item.selected .check { color:#1a5c1a; font-size:13px; font-weight:900; }
.menu-item.unselected { color:#000; font-weight:900; }
.menu-item.unselected .check { color:#555; font-size:13px; font-weight:900; }
.notes-row { margin-top:8px; font-size:12px; font-weight:900; color:#000; border-top:2px dashed #666; padding-top:4px; }
.quote-band { text-align:center; font-size:12px; font-weight:900; font-style:italic; color:#8B1A1A; margin:4px 0 2px; letter-spacing:0.3px; }
.flower-row { text-align:center; font-size:12px; color:#C8A951; letter-spacing:2px; margin:2px 0; font-weight:900; }
.sig-spacer { flex:1; min-height:16px; }
.sig-line { text-align:center; margin-top:10px; font-size:12px; font-weight:900; color:#000; }
.sig-line .sig-underlines { display:flex; justify-content:center; gap:2em; margin-bottom:5px; }
.sig-line .sig-underlines span { display:inline-block; width:140px; border-bottom:2.5px solid #000; }
.sig-line .sig-labels { display:flex; justify-content:center; gap:2em; margin-top:3px; }
.sig-line .sig-labels span { font-weight:900; width:140px; text-align:center; font-size:11px; color:#000; }
.footer { text-align:center; font-size:10.5px; font-weight:900; color:#000; margin-top:8px; border-top:2px dashed #666; padding-top:4px; }
"""

        # ── build menu grid ──────────────────────────────────────────────
        boxes_html = ""
        for cat_title, options in CATEGORIES:
            cat_key = cat_title.split("–")[0].strip()  # "1", "2" … "12"
            chosen_raw = selections.get(cat_key, "") or selections.get(cat_title, "")
            if isinstance(chosen_raw, list):
                chosen_set = set(s.strip() for s in chosen_raw if s.strip())
            elif isinstance(chosen_raw, str) and chosen_raw.strip():
                chosen_set = {chosen_raw.strip()}
            else:
                chosen_set = set()
            box = f"<div class='menu-box'><div class='menu-box-title'>{cat_title}</div>"
            if options:
                for opt in options:
                    is_sel = opt.strip() in chosen_set
                    cls = "selected" if is_sel else "unselected"
                    mark = "✔" if is_sel else "○"
                    box += f"<div class='menu-item {cls}'><span class='check'>{mark}</span>{opt}</div>"
            else:
                val = ", ".join(chosen_set) if chosen_set else "—"
                box += f"<div class='menu-item selected'><span class='check'>✔</span>{val}</div>"
            box += "</div>"
            boxes_html += box

        logo_b64 = self._get_logo_b64()

        return (
            "<!DOCTYPE html><html><head><meta charset='UTF-8'>"
            f"<style>{css}</style>"
            "<script>window.onload=function(){{setTimeout(function(){{window.print();}},600);}};</script>"
            "</head><body>"
            "<div class='page-frame'>"
            "<span class='corner tl'>❀</span>"
            "<span class='corner tr'>❀</span>"
            "<span class='corner bl'>❀</span>"
            "<span class='corner br'>❀</span>"
            "<div class='vine-top'>✿ ❦ ✾ ❧ ✿ ❦ ✾ ❧ ✿ ❦ ✾ ❧ ✿</div>"
            f"<div class='logo-wrap'><img src='{logo_b64}' alt='DBH'/></div>"
            f"<div class='hall-name'>{hall}</div>"
            f"<div class='hall-sub'>{addr}</div>"
            f"<div class='hall-sub'>{ph1}&nbsp;&nbsp;{ph2}</div>"
            "<div class='doc-title'>Food Per Head — Menu Order Sheet</div>"
            f"<div class='booking-ref'>Customer: <b>{cname}</b>&nbsp;&nbsp;|&nbsp;&nbsp;Date: <b>{created}</b></div>"
            f"<div class='menu-grid'>{boxes_html}</div>"
            + (f"<div class='notes-row'><b>Notes:</b> {notes}</div>" if notes else "")
            + "<div class='flower-row'>❀ ✿ ❀ ✿ ❀ ✿ ❀</div>"
            "<div class='quote-band'>\"May your union be filled with love, laughter, and a table always full of blessings.\"</div>"
            "<div class='flower-row'>❀ ✿ ❀ ✿ ❀ ✿ ❀</div>"
            "<div class='sig-spacer'></div>"
            "<div class='sig-line'>"
            "<div class='sig-underlines'>"
            "<span>&nbsp;</span><span>&nbsp;</span><span>&nbsp;</span>"
            "</div>"
            "<div class='sig-labels'>"
            "<span>Party Signature</span> <span>Administrator</span> <span>Kitchen</span>"
            "</div>"
            "</div>"
            f"<div class='footer'>{hall} · {addr} — FPH Menu Sheet printed {_dt.datetime.now().strftime('%d-%b-%Y %I:%M %p')}</div>"
            "<div class='vine-top' style='margin-top:8px;'>✿ ❦ ✾ ❧ ✿ ❦ ✾ ❧ ✿ ❦ ✾ ❧ ✿</div>"
            "</div>"  # page-frame
            "</body></html>"
        )

    def _get_logo_b64(self) -> str:
        """Return the embedded DBH logo as a data-URI string."""
        return "data:image/jpeg;base64,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"


    def clearance_text(self, b: dict, final_payment: float, cleared_at: str, discount: float = 0.0, surplus: float = 0.0) -> str:
        """
        Text version of final clearance receipt (fallback if reportlab missing).
        Wider format — 60 chars — suitable for A4 via Notepad.
        """
        W    = 60
        sep  = "-" * W
        sep2 = "=" * W
        hall = self._hall("hall_name","Dhanak Banquet Hall")
        addr = self._hall("hall_address","Khanewal, Pakistan")
        ph   = self._hall("hall_phone1","") + "  " + self._hall("hall_phone2","")

        gross_total    = (b.get("persons",0) or 0) * (b.get("rate",0) or 0)
        discount       = float(discount or 0)
        surplus        = float(surplus or 0)
        disc_pct       = round((discount / gross_total * 100), 2) if gross_total > 0 else 0
        net_total      = max(0.0, gross_total - discount + surplus)
        advance        = float(b.get("advance",0) or 0)
        total_received = advance + final_payment

        lines = [
            sep2,
            hall.center(W),
            addr.center(W),
            ph.center(W),
            sep2,
            "FINAL CLEARANCE RECEIPT".center(W),
            "*** PROOF OF FULL PAYMENT ***".center(W),
            sep,
            f"Booking #       : {b['id']}",
            f"Booking Date    : {b.get('booking_time','')}",
            f"Clearance Date  : {cleared_at}",
            sep,
            "CUSTOMER",
            f"Name            : {b.get('customer_name','')}",
            f"Phone           : {b.get('phone','')}",
            f"CNIC            : {b.get('cnic','')}",
            f"Home Address    : {b.get('home_address','') or '—'}",
            sep,
            "EVENT DETAILS",
            f"Event Date      : {b.get('event_date','')}  ({b.get('shift','')} Shift)",
            f"Event Type      : {b.get('event_type','')}",
            f"Menu            : {b.get('menu_type','')}",
            f"No. of Persons  : {b.get('persons',0)}",
            f"Rate per Head   : {self._fmt(b.get('rate',0))}",
            sep,
            "PAYMENT CLEARED",
            f"Gross Total     : {self._fmt(gross_total)}",
        ] + ([
            f"Discount        : {self._fmt(discount)}",
        ] if discount > 0 else []) + ([
            f"Surplus (Seating): {self._fmt(surplus)}",
        ] if surplus > 0 else []) + ([
            f"Net Payable     : {self._fmt(net_total)}",
        ] if (discount > 0 or surplus > 0) else []) + [
            f"Advance Paid    : {self._fmt(advance)}",
            f"Final Payment   : {self._fmt(final_payment)}",
            f"Total Received  : {self._fmt(total_received)}",
            f"Balance Due     : {self._fmt(net_total - total_received)}",
            sep2,
            "*** PAYMENT CLEARED IN FULL ***".center(W),
            sep2,
            "",
            "Authorized Signature: ___________________________",
            "",
            "Stamp:",
            "",
            "",
            sep,
            "This document serves as official proof of payment.".center(W),
            f"{hall} — {addr}".center(W),
            sep2,
        ]
        # filter out any None values (from conditional discount lines if any)
        lines = [l for l in lines if l is not None]
        return "\n".join(lines)

    def save_clearance_pdf(self, b: dict, final_payment: float,
                           cleared_at: str, filepath: str,
                           discount: float = 0.0, surplus: float = 0.0) -> bool:
        """
        A4 formal clearance PDF — proof of full payment.
        Suitable for inkjet/laser printer. PRA-compliant layout.
        """
        if not PDF_OK:
            return False
        try:
            os.makedirs(os.path.dirname(filepath) if os.path.dirname(filepath) else ".", exist_ok=True)

            def _draw_floral_border(canvas, doc):
                canvas.saveState()
                W, H = A4
                gold_c  = colors.HexColor(GOLD)
                gold_lt = colors.HexColor("#D4B96A")
                canvas.setStrokeColor(gold_c)
                canvas.setFillColor(gold_c)
                canvas.setLineWidth(1.8)
                canvas.rect(0.8*cm, 0.8*cm, W - 1.6*cm, H - 1.6*cm, stroke=1, fill=0)
                canvas.setLineWidth(0.5)
                canvas.rect(1.1*cm, 1.1*cm, W - 2.2*cm, H - 2.2*cm, stroke=1, fill=0)

                def corner_flower(cx, cy):
                    canvas.setFillColor(gold_c)
                    canvas.circle(cx, cy, 0.22*cm, stroke=0, fill=1)
                    for ang in range(0, 360, 45):
                        rad = math.radians(ang)
                        px = cx + 0.42*cm * math.cos(rad)
                        py = cy + 0.42*cm * math.sin(rad)
                        canvas.circle(px, py, 0.1*cm, stroke=0, fill=1)
                    canvas.setFillColor(colors.white)
                    canvas.circle(cx, cy, 0.1*cm, stroke=0, fill=1)

                for cx_, cy_ in [(0.8*cm, 0.8*cm), (W-0.8*cm, 0.8*cm),
                                  (0.8*cm, H-0.8*cm), (W-0.8*cm, H-0.8*cm)]:
                    corner_flower(cx_, cy_)

                canvas.setFillColor(gold_lt)
                canvas.setStrokeColor(gold_lt)
                canvas.setLineWidth(0.4)

                petal_w, petal_h = 0.09*cm, 0.14*cm
                step = 14

                def draw_petals_h(y_pos, x_start, x_end):
                    x = x_start
                    while x < x_end:
                        p = canvas.beginPath()
                        p.moveTo(x, y_pos + petal_h)
                        p.curveTo(x + petal_w, y_pos + petal_h*1.4,
                                  x + petal_w*2, y_pos + petal_h,
                                  x + petal_w*2, y_pos)
                        p.curveTo(x + petal_w*2, y_pos - petal_h,
                                  x + petal_w, y_pos - petal_h*1.4,
                                  x, y_pos - petal_h)
                        p.curveTo(x - petal_w, y_pos - petal_h*1.4,
                                  x - petal_w*2, y_pos - petal_h,
                                  x - petal_w*2, y_pos)
                        p.curveTo(x - petal_w*2, y_pos + petal_h,
                                  x - petal_w, y_pos + petal_h*1.4,
                                  x, y_pos + petal_h)
                        canvas.drawPath(p, stroke=0, fill=1)
                        small = canvas.beginPath()
                        small.moveTo(x + step*0.5, y_pos)
                        small.curveTo(x + step*0.5, y_pos + 0.06*cm,
                                      x + step*0.5 + 0.06*cm, y_pos + 0.06*cm,
                                      x + step*0.5 + 0.06*cm, y_pos)
                        small.curveTo(x + step*0.5 + 0.06*cm, y_pos - 0.06*cm,
                                      x + step*0.5, y_pos - 0.06*cm,
                                      x + step*0.5, y_pos)
                        canvas.drawPath(small, stroke=0, fill=1)
                        x += step

                def draw_petals_v(x_pos, y_start, y_end):
                    y = y_start
                    while y < y_end:
                        p = canvas.beginPath()
                        p.moveTo(x_pos - petal_h, y)
                        p.curveTo(x_pos - petal_h*1.4, y + petal_w,
                                  x_pos - petal_h, y + petal_w*2,
                                  x_pos, y + petal_w*2)
                        p.curveTo(x_pos + petal_h, y + petal_w*2,
                                  x_pos + petal_h*1.4, y + petal_w,
                                  x_pos + petal_h, y)
                        p.curveTo(x_pos + petal_h*1.4, y - petal_w,
                                  x_pos + petal_h, y - petal_w*2,
                                  x_pos, y - petal_w*2)
                        p.curveTo(x_pos - petal_h, y - petal_w*2,
                                  x_pos - petal_h*1.4, y - petal_w,
                                  x_pos - petal_h, y)
                        canvas.drawPath(p, stroke=0, fill=1)
                        y += step

                margin_top    = H - 0.95*cm
                margin_bottom = 0.95*cm
                margin_left   = 0.95*cm
                margin_right  = W - 0.95*cm
                inner_x_l = 1.4*cm
                inner_x_r = W - 1.4*cm
                inner_y_b = 1.4*cm
                inner_y_t = H - 1.4*cm

                draw_petals_h(margin_top,    inner_x_l, inner_x_r)
                draw_petals_h(margin_bottom, inner_x_l, inner_x_r)
                draw_petals_v(margin_left,   inner_y_b, inner_y_t)
                draw_petals_v(margin_right,  inner_y_b, inner_y_t)

                canvas.restoreState()

            frame = Frame(2.2*cm, 1.8*cm, A4[0]-4.4*cm, A4[1]-3.6*cm, id="main")
            tpl   = PageTemplate(id="floral", frames=[frame], onPage=_draw_floral_border)
            doc   = BaseDocTemplate(filepath, pagesize=A4,
                                    topMargin=1.8*cm, bottomMargin=1.8*cm,
                                    leftMargin=2.2*cm, rightMargin=2.2*cm)
            doc.addPageTemplates([tpl])
            ss        = getSampleStyleSheet()
            gold      = colors.HexColor(GOLD)
            dark      = colors.HexColor("#1F2937")
            green_clr = colors.HexColor("#065F46")

            gross_total    = (b.get("persons",0) or 0) * (b.get("rate",0) or 0)
            discount       = float(discount or 0)
            surplus        = float(surplus or 0)
            disc_pct       = round((discount / gross_total * 100), 2) if gross_total > 0 else 0
            net_total      = max(0.0, gross_total - discount + surplus)
            advance        = float(b.get("advance",0) or 0)
            total_received = advance + final_payment
            balance        = max(0.0, net_total - total_received)

            story = []

                                                                       
                                            
            _logo_para = None
            if PIL_OK:
                for _lp in ["dhanak_logo.png",
                             os.path.join(os.path.dirname(os.path.abspath(__file__)), "dhanak_logo.png")]:
                    if os.path.exists(_lp):
                        try:
                            from reportlab.platypus import Image as RLImage
                            _logo_para = RLImage(_lp, width=2.2*cm, height=2.2*cm)
                            break
                        except Exception:
                            pass

            hall_name_para = Paragraph(
                f"<b>{self._hall('hall_name','Dhanak Banquet Hall')}</b>",
                ParagraphStyle("h", parent=ss["Normal"], fontSize=20,
                               textColor=gold, fontName="Helvetica-Bold"))
            hall_info_para = Paragraph(
                f"{self._hall('hall_address','')}<br/>"
                f"Tel: {self._hall('hall_phone1','')}  |  {self._hall('hall_phone2','')}"
                + (f"<br/>PRA STRN: {self._hall('hall_strn')}" if self._hall("hall_strn") else ""),
                ParagraphStyle("ha", parent=ss["Normal"], fontSize=10,
                               textColor=colors.gray, alignment=TA_RIGHT))

            if _logo_para:
                header_data = [[_logo_para, hall_name_para, hall_info_para]]
                h_tbl = Table(header_data, colWidths=[2.5*cm, 7*cm, 7.5*cm])
            else:
                header_data = [[hall_name_para, hall_info_para]]
                h_tbl = Table(header_data, colWidths=[9.5*cm, 7.5*cm])
            h_tbl.setStyle(TableStyle([
                ("VALIGN", (0,0),(-1,-1), "MIDDLE"),
                ("LINEBELOW", (0,0),(-1,0), 2, gold),
                ("BOTTOMPADDING", (0,0),(-1,0), 10),
            ]))
            story.append(h_tbl)
            story.append(Spacer(1, 0.5*cm))

                                                                       
            paid_style = ParagraphStyle("paid", parent=ss["Normal"],
                                         fontSize=22, textColor=colors.white,
                                         fontName="Helvetica-Bold",
                                         alignment=TA_CENTER)
            paid_tbl = Table(
                [[Paragraph("✓  PAYMENT CLEARED IN FULL", paid_style)]],
                colWidths=[17*cm])
            paid_tbl.setStyle(TableStyle([
                ("BACKGROUND",    (0,0),(0,0), green_clr),
                ("TOPPADDING",    (0,0),(0,0), 12),
                ("BOTTOMPADDING", (0,0),(0,0), 12),
                ("ROUNDEDCORNERS",[8]),
            ]))
            story.append(paid_tbl)
            story.append(Spacer(1, 0.5*cm))

                                                                       
            meta_data = [
                ["FINAL CLEARANCE RECEIPT",
                 f"Booking #:  {b['id']}"],
                [f"Clearance Date:  {cleared_at}",
                 f"Booking Date:  {b.get('booking_time','')}"],
            ]
            meta_tbl = Table(meta_data, colWidths=[9*cm, 8*cm])
            meta_tbl.setStyle(TableStyle([
                ("FONTNAME",    (0,0),(0,0), "Helvetica-Bold"),
                ("FONTSIZE",    (0,0),(-1,-1), 11),
                ("TEXTCOLOR",   (0,0),(0,0), dark),
                ("TEXTCOLOR",   (1,0),(1,0), dark),
                ("TEXTCOLOR",   (0,1),(-1,1), colors.gray),
                ("TOPPADDING",  (0,0),(-1,-1), 4),
                ("BOTTOMPADDING",(0,0),(-1,-1),4),
            ]))
            story.append(meta_tbl)
            story.append(Spacer(1, 0.3*cm))

                                                                       
            def section(title, rows, highlight_last=False):
                data = [[title, ""]] + rows
                col_w = [8*cm, 9*cm]
                t = Table(data, colWidths=col_w)
                style = [
                    ("BACKGROUND",    (0,0),(1,0),  colors.HexColor("#374151")),
                    ("TEXTCOLOR",     (0,0),(1,0),  colors.white),
                    ("FONTNAME",      (0,0),(1,0),  "Helvetica-Bold"),
                    ("SPAN",          (0,0),(1,0)),
                    ("FONTSIZE",      (0,0),(-1,-1), 10),
                    ("TOPPADDING",    (0,0),(-1,-1), 6),
                    ("BOTTOMPADDING", (0,0),(-1,-1), 6),
                    ("LEFTPADDING",   (0,0),(-1,-1), 10),
                    ("ROWBACKGROUNDS",(0,1),(-1,-1),
                     [colors.white, colors.HexColor("#F9FAFB")]),
                    ("LINEBELOW",     (0,-1),(1,-1), 0.5, colors.lightgrey),
                ]
                if highlight_last and len(data) > 1:
                    last = len(data) - 1
                    style += [
                        ("BACKGROUND", (0,last),(1,last), colors.HexColor("#D1FAE5")),
                        ("FONTNAME",   (0,last),(1,last), "Helvetica-Bold"),
                        ("TEXTCOLOR",  (0,last),(1,last), green_clr),
                    ]
                t.setStyle(TableStyle(style))
                return t

                      
            story.append(section("CUSTOMER INFORMATION", [
                ["Booking #",    f"#{b.get('id','—')}"],
                ["Booked On",    b.get("booking_time","") or "—"],
                ["Name",         b.get("customer_name","")],
                ["CNIC",         b.get("cnic","") or "—"],
                ["Phone",        b.get("phone","") or "—"],
                ["Home Address", b.get("home_address","") or "—"],
            ]))
            story.append(Spacer(1, 0.3*cm))

                   
            story.append(section("EVENT DETAILS", [
                ["Event Date",     f"{b.get('event_date','')}  ({b.get('shift','')} Shift)"],
                ["Event Type",     b.get("event_type","")],
                ["Menu Type",      b.get("menu_type","")],
                ["No. of Persons", str(b.get("persons",0))],
                ["Rate per Head",  self._fmt(b.get("rate",0))],
            ]))
            story.append(Spacer(1, 0.3*cm))

                             
            pay_rows = [["Gross Total Bill", self._fmt(gross_total)]]
            if discount > 0:
                pay_rows.append(["Discount", f"- {self._fmt(discount)}"])
            if surplus > 0:
                pay_rows.append(["Surplus Charge (Seating)", self._fmt(surplus)])
            if discount > 0 or surplus > 0:
                pay_rows.append(["Net Payable", self._fmt(net_total)])
            pay_rows += [
                ["Advance Paid",      self._fmt(advance)],
                ["Final Payment",     self._fmt(final_payment)],
                ["Total Received",    self._fmt(total_received)],
                ["Balance Remaining", self._fmt(balance)],
            ]
            story.append(section("PAYMENT BREAKDOWN", pay_rows, highlight_last=True))
            story.append(Spacer(1, 0.6*cm))

                                    
            sig_data = [
                ["Authorized Signature", "Official Stamp"],
                ["\n\n\n________________________", ""],
            ]
            sig_tbl = Table(sig_data, colWidths=[8.5*cm, 8.5*cm])
            sig_tbl.setStyle(TableStyle([
                ("FONTNAME",    (0,0),(-1,0), "Helvetica-Bold"),
                ("FONTSIZE",    (0,0),(-1,-1), 10),
                ("TEXTCOLOR",   (0,0),(-1,0), dark),
                ("ALIGN",       (0,0),(-1,-1), "CENTER"),
                ("TOPPADDING",  (0,0),(-1,-1), 6),
                ("BOX",         (0,1),(0,1),   0.5, colors.grey),
                ("BOX",         (1,1),(1,1),   0.5, colors.grey),
                ("TOPPADDING",  (0,1),(-1,1),  30),
                ("BOTTOMPADDING",(0,1),(-1,1), 10),
            ]))
            story.append(sig_tbl)
            story.append(Spacer(1, 0.4*cm))

                    
            footer_style = ParagraphStyle("ft", parent=ss["Normal"],
                                           fontSize=8, textColor=colors.gray,
                                           alignment=TA_CENTER)
            story.append(Paragraph(
                "This is a computer-generated document and serves as official proof of payment. "
                f"Thank you for choosing {self._hall('hall_name','Dhanak Banquet Hall')}. "
                "We hope to see you again!",
                footer_style))

            doc.build(story)
            return True
        except Exception as e:
            print(f"Clearance PDF error: {e}")
            return False

                                                                      
    def save_pdf(self, b: dict, filepath: str) -> bool:
        if not PDF_OK:
            return False
        try:
            os.makedirs(os.path.dirname(filepath) if os.path.dirname(filepath) else ".", exist_ok=True)
            doc  = SimpleDocTemplate(filepath, pagesize=A4,
                                     topMargin=1.5*cm, bottomMargin=1.5*cm,
                                     leftMargin=2*cm, rightMargin=2*cm)
            ss   = getSampleStyleSheet()
            gold_col = colors.HexColor("#C5A059")
            dark_col = colors.HexColor("#1F2937")

            title_style = ParagraphStyle("title", parent=ss["Normal"],
                                          fontSize=18, textColor=gold_col,
                                          alignment=TA_CENTER, fontName="Helvetica-Bold",
                                          spaceAfter=4)
            sub_style   = ParagraphStyle("sub", parent=ss["Normal"],
                                          fontSize=10, textColor=colors.gray,
                                          alignment=TA_CENTER, spaceAfter=2)
            head_style  = ParagraphStyle("head", parent=ss["Normal"],
                                          fontSize=10, textColor=colors.white,
                                          fontName="Helvetica-Bold")
            normal      = ParagraphStyle("norm", parent=ss["Normal"],
                                          fontSize=10, textColor=dark_col)

            total = (b.get("persons",0) or 0) * (b.get("rate",0) or 0)
            rem   = max(0, total - (b.get("advance",0) or 0) - (b.get("final_payment",0) or 0))

            story = []

                                       
            _logo_para2 = None
            if PIL_OK:
                for _lp in ["dhanak_logo.png",
                             os.path.join(os.path.dirname(os.path.abspath(__file__)), "dhanak_logo.png")]:
                    if os.path.exists(_lp):
                        try:
                            from reportlab.platypus import Image as RLImage
                            _logo_para2 = RLImage(_lp, width=1.6*cm, height=1.6*cm)
                            break
                        except Exception:
                            pass

            if _logo_para2:
                logo_name_para = Paragraph(
                    self.cfg.get("hall_name","Dhanak Banquet Hall"), title_style)
                logo_row = Table([[_logo_para2, logo_name_para]],
                                  colWidths=[1.9*cm, 15.1*cm])
                logo_row.setStyle(TableStyle([("VALIGN",(0,0),(-1,-1),"MIDDLE")]))
                story.append(logo_row)
            else:
                story.append(Paragraph(self.cfg.get("hall_name","Dhanak Banquet Hall"), title_style))
            story.append(Paragraph(self.cfg.get("hall_address",""), sub_style))
            story.append(Paragraph(
                f"Tel: {self.cfg.get('hall_phone1','')}  |  {self.cfg.get('hall_phone2','')}",
                sub_style))
            if self.cfg.get("hall_strn"):
                story.append(Paragraph(f"PRA STRN: {self.cfg.get('hall_strn')}", sub_style))
            story.append(Spacer(1, 0.4*cm))

                               
            inv_table = Table(
                [[f"TAX INVOICE — Booking #{b['id']}",
                  f"Date: {b.get('booking_time','')[:11]}"]],
                colWidths=[12*cm, 5*cm])
            inv_table.setStyle(TableStyle([
                ("BACKGROUND",  (0,0), (-1,-1), gold_col),
                ("TEXTCOLOR",   (0,0), (-1,-1), colors.white),
                ("FONTNAME",    (0,0), (-1,-1), "Helvetica-Bold"),
                ("FONTSIZE",    (0,0), (-1,-1), 11),
                ("ALIGN",       (1,0), (1,0),   "RIGHT"),
                ("TOPPADDING",  (0,0), (-1,-1), 6),
                ("BOTTOMPADDING",(0,0),(-1,-1), 6),
                ("LEFTPADDING", (0,0), (-1,-1), 10),
            ]))
            story.append(inv_table)
            story.append(Spacer(1, 0.3*cm))

                                      
            def section(title, rows):
                data = [[title, ""]] + rows
                t = Table(data, colWidths=[4*cm, 12*cm])
                t.setStyle(TableStyle([
                    ("BACKGROUND",  (0,0),(1,0),  colors.HexColor("#374151")),
                    ("TEXTCOLOR",   (0,0),(1,0),  colors.white),
                    ("FONTNAME",    (0,0),(1,0),  "Helvetica-Bold"),
                    ("SPAN",        (0,0),(1,0)),
                    ("FONTSIZE",    (0,0),(-1,-1), 10),
                    ("TOPPADDING",  (0,0),(-1,-1), 5),
                    ("BOTTOMPADDING",(0,0),(-1,-1),5),
                    ("LEFTPADDING", (0,0),(-1,-1), 8),
                    ("LINEBELOW",   (0,-1),(1,-1), 0.5, colors.lightgrey),
                    ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white, colors.HexColor("#F9FAFB")]),
                ]))
                return t

            story.append(section("CUSTOMER INFORMATION", [
                ["Name",    b.get("customer_name","")],
                ["CNIC",    b.get("cnic","") or "—"],
                ["Phone",   b.get("phone","") or "—"],
            ]))
            story.append(Spacer(1, 0.3*cm))

            story.append(section("EVENT DETAILS", [
                ["Event Date", f"{b.get('event_date','')}  ({b.get('shift','')} Shift)"],
                ["Event Type", b.get("event_type","")],
                ["Menu Type",  b.get("menu_type","")],
                ["No. of Persons", str(b.get("persons",0))],
            ]))
            story.append(Spacer(1, 0.3*cm))

                           
            pay_data = [
                ["DESCRIPTION", "AMOUNT"],
                [f"Rate per head: Rs. {b.get('rate',0):,.0f} × {b.get('persons',0)} persons",
                 self._fmt(total)],
                ["Advance Received", f"({self._fmt(b.get('advance',0))})"],
                ["Balance Remaining", self._fmt(rem)],
                ["", ""],
                ["PRA Sales Tax (5%)", self._fmt(b.get("pra_tax",0))],
                [f"FBR Income Tax ({10 if b.get('filer_status')=='Filer' else 20}%)",
                 self._fmt(b.get("fbr_tax",0))],
                [f"Tax Status: {b.get('filer_status','Non-Filer')}", ""],
            ]
            pay_table = Table(pay_data, colWidths=[11*cm, 6*cm])
            pay_table.setStyle(TableStyle([
                ("BACKGROUND",  (0,0),(1,0),  gold_col),
                ("TEXTCOLOR",   (0,0),(1,0),  colors.white),
                ("FONTNAME",    (0,0),(1,0),  "Helvetica-Bold"),
                ("FONTSIZE",    (0,0),(-1,-1), 10),
                ("ALIGN",       (1,0),(1,-1), "RIGHT"),
                ("TOPPADDING",  (0,0),(-1,-1), 5),
                ("BOTTOMPADDING",(0,0),(-1,-1),5),
                ("LEFTPADDING", (0,0),(-1,-1), 8),
                ("LINEBELOW",   (0,1),(1,1),  0.5, colors.grey),
                ("LINEABOVE",   (0,4),(1,4),  0.5, colors.lightgrey),
                ("FONTNAME",    (0,2),(1,2),  "Helvetica-Oblique"),
                ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white, colors.HexColor("#F9FAFB")]),
            ]))
            story.append(pay_table)
            story.append(Spacer(1, 0.5*cm))

                    
            if b.get("notes"):
                story.append(Paragraph(f"<b>Notes:</b> {b['notes']}", normal))
                story.append(Spacer(1, 0.3*cm))

            story.append(Paragraph(
                "This is a computer-generated document. "
                "Thank you for choosing " + self.cfg.get("hall_name","Dhanak Banquet Hall") + ".",
                ParagraphStyle("footer", parent=ss["Normal"],
                               fontSize=9, textColor=colors.gray,
                               alignment=TA_CENTER)))

            doc.build(story)
            return True
        except Exception as e:
            print(f"PDF error: {e}")
            return False

                                                                      
                  
                                                                      

class Voice:
    """
    Voice assistant — ONE job: understand a date, check DB, report shifts.
    TTS: edge-tts (neural) played via Windows MCI (no window). pyttsx3 fallback.
    Mic: smart listen — stops on silence, hard cap 3 seconds.
    """

    def __init__(self, db: DB, cfg: Config):
        self.db  = db
        self.cfg = cfg
        self.tts = None
        if TTS_OK:
            try:
                self.tts = pyttsx3.init()
                self.tts.setProperty("rate", 165)
            except: pass

    # ──────────────── TTS ─────────────────────────────────────────────
    def speak(self, text):
        clean = re.sub(r'\s+', ' ', text).strip()
        if not clean:
            return
        def _do():
            # Try edge-tts first (natural Microsoft neural voice)
            if EDGE_TTS_OK:
                try:
                    self._speak_edge(clean)
                    return
                except Exception as ex:
                    pass  # fall through to pyttsx3
            # Fallback: pyttsx3 (robotic but always works offline)
            if self.tts:
                try:
                    self.tts.say(clean)
                    self.tts.runAndWait()
                except: pass
        threading.Thread(target=_do, daemon=True).start()

    def _speak_edge(self, text):
        """Generate speech with edge-tts, play via Windows MCI (silent, no window)."""
        tmp_path = os.path.join(tempfile.gettempdir(), "dhanak_tts.mp3")

        # Generate mp3 with edge-tts
        async def _gen():
            comm = edge_tts.Communicate(text, "en-US-GuyNeural")
            await comm.save(tmp_path)

        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(_gen())
        finally:
            loop.close()

        if not os.path.exists(tmp_path) or os.path.getsize(tmp_path) < 500:
            raise RuntimeError("edge-tts produced no audio")

        # Play on Windows via MCI (no popup, no external player needed)
        if sys.platform == "win32":
            self._play_mci(tmp_path)
        else:
            try:
                subprocess.run(["afplay", tmp_path], timeout=20, capture_output=True)
            except Exception:
                subprocess.run(["mpg123", "-q", tmp_path], timeout=20, capture_output=True)

    @staticmethod
    def _play_mci(filepath):
        """Play an mp3 file silently on Windows using MCI (Media Control Interface)."""
        import ctypes
        mci = ctypes.windll.winmm.mciSendStringW
        # Close any previous playback
        mci('close dhanak_tts', 0, 0, 0)
        # Open and play (wait = synchronous, blocks until done)
        fp = filepath.replace('\\', '/')
        ret = mci(f'open "{fp}" type mpegvideo alias dhanak_tts', 0, 0, 0)
        if ret != 0:
            # Fallback: try os.startfile
            os.startfile(filepath)
            return
        mci('play dhanak_tts wait', 0, 0, 0)
        mci('close dhanak_tts', 0, 0, 0)

    # ──────────────── Microphone: smart stop + 3 sec hard cap ─────────
    def listen(self) -> str:
        if not SR_OK:
            raise RuntimeError("SpeechRecognition not installed.")
        r = sr.Recognizer()
        r.energy_threshold  = 400
        r.pause_threshold   = 0.6     # stop 0.6s after speech ends
        r.dynamic_energy_threshold = True
        with sr.Microphone() as src:
            r.adjust_for_ambient_noise(src, duration=0.3)
            # timeout=3: give up if no speech within 3s
            # phrase_time_limit=3: hard cap speech at 3s even if still talking
            audio = r.listen(src, timeout=3, phrase_time_limit=3)
        return r.recognize_google(audio, language="en-US")

    # ──────────────── Claude: extract date ONLY ───────────────────────
    def _parse_date(self, text: str) -> dict:
        if not CLAUDE_OK:
            raise RuntimeError("anthropic not installed.")
        key = self.cfg.get("api_key", "")
        if not key:
            raise RuntimeError("No API key. Go to Settings.")
        client = anthropic.Anthropic(api_key=key)
        today  = datetime.date.today()
        yr     = today.year

        prompt = f"""Today is {today.strftime('%d %B %Y')} ({today.strftime('%A')}).
Extract the date from the user's text. Understand English, Urdu, Roman Urdu.
"kal"=tomorrow, "parson"=day after tomorrow, "aglay jumma"=next Friday, etc.

Return ONLY JSON, nothing else:
For a specific date: {{"date":"YYYY-MM-DD","month":null}}
For a whole month:   {{"date":null,"month":"April","year":{yr}}}
If unclear:          {{"date":null,"month":null}}"""

        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=60,
            system=prompt,
            messages=[{"role": "user", "content": text}]
        )
        raw = msg.content[0].text.strip()
        raw = re.sub(r"```json|```", "", raw).strip()
        return json.loads(raw)

    # ──────────────── Format shifts as a list ─────────────────────────
    @staticmethod
    def _format_shifts(nice_date, taken, av):
        """
        Format availability as a clean per-shift list:
          16 March 2026 — 1 shift booked
          Day 1    : BOOKED
          Day 2    : Available
          Night 1  : Available
          Night 2  : Available
        """
        booked_count = len(taken)
        if av["full"]:
            header = f"{nice_date} — All 4 shifts booked"
        elif av["open"]:
            header = f"{nice_date} — All shifts available"
        else:
            header = f"{nice_date} — {booked_count} shift{'s' if booked_count != 1 else ''} booked"

        lines = [header]
        for s in SHIFTS:
            if s in taken:
                lines.append(f"  {s:<10}: BOOKED")
            else:
                lines.append(f"  {s:<10}: Available")
        return "\n".join(lines)

    # ──────────────── Main handler: date → DB → formatted reply ───────
    def handle(self, text: str) -> str:
        try:
            parsed = self._parse_date(text)
        except json.JSONDecodeError:
            return "Could not understand. Try: 15 March ko shifts? or April mein dates?"
        except Exception as e:
            return f"Error: {e}"

        # ── Single date ──
        if parsed.get("date"):
            ds = parsed["date"]
            av = self.db.availability(ds)
            try:
                nice = datetime.date.fromisoformat(ds).strftime("%d %B %Y")
            except:
                nice = ds
            taken = av["taken"]
            return self._format_shifts(nice, taken, av)

        # ── Whole month ──
        if parsed.get("month"):
            mn = parsed["month"]
            yr = int(parsed.get("year", datetime.date.today().year))
            try:
                mi = MONTHS.index(mn) + 1
            except:
                return f"Could not understand month: {mn}"
            amap  = self.db.month_avail(yr, mi)
            total = calendar.monthrange(yr, mi)[1]
            free  = [d for d in range(1, total+1) if d not in amap]
            part  = [d for d in range(1, total+1) if d in amap and len(amap[d]) < 4]
            full  = [d for d in range(1, total+1) if d in amap and len(amap[d]) >= 4]
            parts = [f"{mn} {yr}:"]
            if free:
                parts.append(f"{len(free)} fully free dates." if len(free) > 8
                             else f"Free: {', '.join(map(str, free))}.")
            if part:
                parts.append(f"{len(part)} partially booked.")
            if full:
                parts.append(f"{len(full)} fully booked.")
            if not free and not part:
                return f"{mn} {yr}: Completely booked."
            return " ".join(parts)

        return "Could not understand a date. Try: 15 March ko shifts? or April mein dates?"

                                                                      
             
                                                                      

def btn(parent, text, cmd, w=150, h=42, size=18, color=GOLD, hcolor=GOLD_H, tcolor="#1E1B10"):
    return ctk.CTkButton(parent, text=text, command=cmd,
                         width=w, height=h,
                         fg_color=color, hover_color=hcolor,
                         text_color=tcolor,
                         font=ctk.CTkFont(family="Georgia", size=size, weight="bold"),
                         corner_radius=12)

def sec_lbl(parent, text):
    return ctk.CTkLabel(parent, text=text,
                        font=ctk.CTkFont(family="Georgia", size=17, weight="bold"),
                        text_color=GOLD)

def fld_lbl(parent, text):
    return ctk.CTkLabel(parent, text=text,
                        font=ctk.CTkFont(family="Georgia", size=17),
                        text_color=MUTED, anchor="w")

def entry(parent, ph="", w=200):
    return ctk.CTkEntry(parent, placeholder_text=ph,
                        width=w, height=44,
                        fg_color=CARD2, border_color=BORDER,
                        text_color=WHITE,
                        placeholder_text_color=MUTED,
                        font=ctk.CTkFont(family="Inter", size=18))

def cbo(parent, vals, w=200):
    return ctk.CTkComboBox(parent, values=vals, width=w, height=44,
                           fg_color=CARD2, border_color=BORDER,
                           button_color=GOLD_DK, button_hover_color=GOLD,
                           dropdown_fg_color=PANEL,
                           dropdown_text_color=WHITE,
                           text_color=WHITE,
                           font=ctk.CTkFont(family="Inter", size=18))

def tree_setup(parent, cols, widths):
    style = ttk.Style()
    style.theme_use("clam")
    style.configure("D.Treeview",
                    background=CARD, foreground=WHITE,
                    fieldbackground=CARD, rowheight=40,
                    font=("Inter", 13))
    style.configure("D.Treeview.Heading",
                    background=PANEL, foreground=GOLD,
                    font=("Georgia", 14, "bold"), relief="flat")
    style.map("D.Treeview",
              background=[("selected", GOLD)],
              foreground=[("selected", "#1E1B10")])
    tv = ttk.Treeview(parent, columns=cols, show="headings", style="D.Treeview")
    for c, w in zip(cols, widths):
        tv.heading(c, text=c)
        tv.column(c, width=w, anchor="center")
    # Inset/coffered effect via alternating row backgrounds
    style.configure("D.Treeview",
                    rowheight=40)
    style.map("D.Treeview",
              background=[("!selected", CARD)],
              foreground=[("!selected", WHITE)])
    style.configure("D.Treeview",
                    rowheight=40)
    tv.tag_configure("status_cleared", foreground=GREEN)
    tv.tag_configure("status_pending", foreground=ORANGE)
    tv.tag_configure("status_neutral", foreground=MUTED)
    tv.tag_configure("status_cancelled", foreground=RED)

    sb = ttk.Scrollbar(parent, orient="vertical", command=tv.yview)
    tv.configure(yscrollcommand=sb.set)
    sb.pack(side="right", fill="y")
    tv.pack(fill="both", expand=True)
    return tv


                                                                      
                     
                                                                      

class DatePickerDialog(ctk.CTkToplevel):
    def __init__(self, parent, current_date=None, on_select=None):
        super().__init__(parent)
        self.on_select = on_select
        today = datetime.date.today()
        if current_date and isinstance(current_date, datetime.date):
            self.year, self.month = current_date.year, current_date.month
        else:
            self.year, self.month = today.year, today.month
        self.title("Pick a Date")
        self.geometry("370x400")
        self.configure(fg_color=BG)
        self.grab_set()
        self.resizable(False, False)
        self._build()

    def _build(self):
        nav = ctk.CTkFrame(self, fg_color=BG, corner_radius=12)
        nav.pack(fill="x", padx=10, pady=10)

        btn(nav, "◀", self._prev, w=38, h=34, size=18,
            color=GOLD, hcolor=GOLD_H, tcolor="#1E1B10").pack(side="left", padx=6, pady=6)

        self.month_var = ctk.StringVar(value=MONTHS[self.month-1])
        ctk.CTkOptionMenu(
            nav, variable=self.month_var, values=MONTHS,
            width=120, height=34, fg_color=CARD, button_color=GOLD_DK,
            text_color=WHITE, dropdown_fg_color=PANEL, dropdown_hover_color=GOLD_DK,
            command=self._on_month_change
        ).pack(side="left", padx=4, pady=6)

        self.year_var = ctk.StringVar(value=str(self.year))
        ye = ctk.CTkEntry(nav, textvariable=self.year_var, width=66, height=34,
                          fg_color=CARD, border_color=BORDER, text_color=WHITE,
                          font=ctk.CTkFont(family="Georgia", size=18), justify="center")
        ye.pack(side="left", padx=4, pady=6)
        ye.bind("<Return>",    self._on_year_change)
        ye.bind("<FocusOut>",  self._on_year_change)

        btn(nav, "▶", self._next, w=38, h=34, size=18,
            color=GOLD, hcolor=GOLD_H, tcolor="#1E1B10").pack(side="left", padx=6, pady=6)

        self.grid_frame = ctk.CTkFrame(self, fg_color=BG, corner_radius=12)
        self.grid_frame.pack(fill="both", expand=True, padx=10, pady=(0,10))
        self._draw()

    def _draw(self):
        for w in self.grid_frame.winfo_children(): w.destroy()
        for ci, d in enumerate(["Mo","Tu","We","Th","Fr","Sa","Su"]):
            ctk.CTkLabel(self.grid_frame, text=d, width=44, height=30,
                         font=ctk.CTkFont(family="Georgia", size=17, weight="bold"),
                         text_color=GOLD).grid(row=0, column=ci, padx=2, pady=(8,2))
        first, total = calendar.monthrange(self.year, self.month)
        today = datetime.date.today()
        for day in range(1, total+1):
            d   = datetime.date(self.year, self.month, day)
            wd  = (first + day - 1) % 7
            ro  = 1 + (first + day - 1) // 7
            bg  = GOLD_DK if d == today else CARD
            ctk.CTkButton(
                self.grid_frame, text=str(day), width=44, height=36,
                fg_color=bg, hover_color=GOLD,
                text_color=WHITE, font=ctk.CTkFont(family="Georgia", size=17),
                corner_radius=6,
                command=lambda _d=d: self._select(_d)
            ).grid(row=ro, column=wd, padx=2, pady=2)
        for ci in range(7):
            self.grid_frame.grid_columnconfigure(ci, weight=1)

    def _prev(self):
        self.month -= 1
        if self.month < 1: self.month = 12; self.year -= 1
        self.month_var.set(MONTHS[self.month-1])
        self.year_var.set(str(self.year))
        self._draw()

    def _next(self):
        self.month += 1
        if self.month > 12: self.month = 1; self.year += 1
        self.month_var.set(MONTHS[self.month-1])
        self.year_var.set(str(self.year))
        self._draw()

    def _on_month_change(self, val):
        self.month = MONTHS.index(val) + 1
        self._draw()

    def _on_year_change(self, event=None):
        try:
            self.year = int(self.year_var.get())
            self._draw()
        except: pass

    def _select(self, d):
        if self.on_select:
            self.on_select(d)
        self.destroy()

                                                                      
                                         
                                                                      

class BookingDialog(ctk.CTkToplevel):
    def __init__(self, parent, db: DB, on_done, existing: dict = None):
        super().__init__(parent)
        self.db       = db
        self.on_done  = on_done
        self.existing = existing
        self.title("Edit Booking" if existing else "New Booking")
        self.geometry("720x620")
        self.configure(fg_color=BG)
        self.grab_set()
        self._build()
        if existing:
            self._fill(existing)

    def _build(self):
        scroll = ctk.CTkScrollableFrame(self, fg_color=BG, corner_radius=0)
        scroll.pack(fill="both", expand=True, padx=16, pady=16)

        title = "✏️  Edit Booking" if self.existing else "➕  New Booking"
        ctk.CTkLabel(scroll, text=title,
                     font=ctk.CTkFont(family="Georgia", size=23, weight="bold"),
                     text_color=GOLD).pack(anchor="w", pady=(0,16))

        def row2(lbl1, w1, lbl2, w2):
            r = ctk.CTkFrame(scroll, fg_color="transparent")
            r.pack(fill="x", pady=4)
            c1 = ctk.CTkFrame(r, fg_color="transparent")
            c1.pack(side="left", expand=True, fill="x", padx=(0,8))
            fld_lbl(c1, lbl1).pack(anchor="w")
            c2 = ctk.CTkFrame(r, fg_color="transparent")
            c2.pack(side="left", expand=True, fill="x")
            fld_lbl(c2, lbl2).pack(anchor="w")
            return c1, c2

                  
        sec_lbl(scroll, "▸  CUSTOMER").pack(anchor="w", pady=(8,4))

        r = ctk.CTkFrame(scroll, fg_color="transparent")
        r.pack(fill="x", pady=4)
        fld_lbl(r, "Full Name *").pack(side="left", padx=(0,8))
        self.e_name = entry(r, "Customer name", 300)
        self.e_name.pack(side="left", expand=True, fill="x")

        c1, c2 = row2("CNIC", 200, "Phone", 200)
        self.e_cnic  = entry(c1, "xxxxx-xxxxxxx-x"); self.e_cnic.pack(fill="x")
        self.e_phone = entry(c2, "03xx-xxxxxxx");    self.e_phone.pack(fill="x")

        r2 = ctk.CTkFrame(scroll, fg_color="transparent")
        r2.pack(fill="x", pady=4)
        fld_lbl(r2, "Home Address").pack(side="left", padx=(0,8))
        self.e_addr = entry(r2, "Street, City, etc.", 300)
        self.e_addr.pack(side="left", expand=True, fill="x")

               
        sec_lbl(scroll, "▸  EVENT DETAILS").pack(anchor="w", pady=(16,4))

        date_row = ctk.CTkFrame(scroll, fg_color="transparent")
        date_row.pack(fill="x", pady=4)
        c1 = ctk.CTkFrame(date_row, fg_color="transparent")
        c1.pack(side="left", expand=True, fill="x", padx=(0,8))
        c2 = ctk.CTkFrame(date_row, fg_color="transparent")
        c2.pack(side="left", expand=True, fill="x")

        fld_lbl(c1, "Event Date * (DD/MM/YYYY)").pack(anchor="w")
        date_inner = ctk.CTkFrame(c1, fg_color="transparent")
        date_inner.pack(fill="x")
        self.e_date = entry(date_inner, "DD/MM/YYYY", 150)
        self.e_date.pack(side="left", fill="x", expand=True, padx=(0,6))
        btn(date_inner, "📅", lambda: self._pick_date(), w=38, h=36, size=19,
            color=CARD, hcolor=GOLD_DK, tcolor=WHITE).pack(side="left")

        fld_lbl(c2, "Shift").pack(anchor="w")
        self.e_shift = cbo(c2, SHIFTS); self.e_shift.pack(fill="x"); self.e_shift.set("Day")

        c1, c2 = row2("Persons", 100, "Event Type", 160)
        self.e_pers  = entry(c1, "0");      self.e_pers.pack(fill="x")
        self.e_evt   = cbo(c2, EVENT_TYPES); self.e_evt.pack(fill="x"); self.e_evt.set("Mehndi")

        c1, c2 = row2("Menu Type", 120, "Tax Status", 140)
        self.e_menu  = cbo(c1, MENU_TYPES); self.e_menu.pack(fill="x"); self.e_menu.set("FPH")
        self.e_filer = cbo(c2, FILER_OPTS); self.e_filer.pack(fill="x"); self.e_filer.set("Non-Filer")

                 
        sec_lbl(scroll, "▸  PAYMENT").pack(anchor="w", pady=(16,4))

        c1, c2 = row2("Rate / Head (Rs.)", 140, "Advance Paid (Rs.)", 140)
        self.e_rate = entry(c1, "0"); self.e_rate.pack(fill="x")
        self.e_adv  = entry(c2, "0"); self.e_adv.pack(fill="x")

               
        sec_lbl(scroll, "▸  NOTES").pack(anchor="w", pady=(16,4))
        self.e_notes = ctk.CTkTextbox(scroll, height=60,
                                       fg_color=CARD, text_color=WHITE,
                                       border_color=BORDER,
                                       font=ctk.CTkFont(family="Georgia", size=18))
        self.e_notes.pack(fill="x", pady=4)

                
        self.st_var = ctk.StringVar()
        ctk.CTkLabel(scroll, textvariable=self.st_var,
                     font=ctk.CTkFont(family="Georgia", size=18, weight="bold"),
                     text_color=RED, wraplength=560).pack(pady=4)

                 
        br = ctk.CTkFrame(scroll, fg_color="transparent")
        br.pack(fill="x", pady=8)
        label = "💾  Save Changes" if self.existing else "✅  Confirm Booking"
        btn(br, label, self._submit, w=200, h=42, size=19).pack(side="left", padx=(0,12))
        btn(br, "Cancel", self.destroy, w=100, h=42, size=18,
            color=CARD, hcolor=CARD2, tcolor=MUTED).pack(side="left")

    def _pick_date(self):
        current = None
        try:
            txt = self.e_date.get().strip()
            if txt:
                d, m, y = txt.split("/")
                current = datetime.date(int(y), int(m), int(d))
        except: pass
        def on_sel(d):
            self.e_date.delete(0, "end")
            self.e_date.insert(0, d.strftime("%d/%m/%Y"))
        DatePickerDialog(self, current_date=current, on_select=on_sel)

    def _fill(self, b):
        self.e_name.insert(0, b.get("customer_name",""))
        self.e_cnic.insert(0, b.get("cnic",""))
        self.e_phone.insert(0, b.get("phone",""))
        self.e_addr.insert(0, b.get("home_address",""))
        raw = b.get("event_date","")
        try:
            iso = datetime.date.fromisoformat(raw)
            self.e_date.insert(0, iso.strftime("%d/%m/%Y"))
        except:
            self.e_date.insert(0, raw)
        self.e_shift.set(b.get("shift","Day"))
        self.e_pers.insert(0, str(b.get("persons","0")))
        self.e_evt.set(b.get("event_type","Mehndi"))
        self.e_menu.set(b.get("menu_type","FPH"))
        self.e_filer.set(b.get("filer_status","Non-Filer"))
        self.e_rate.insert(0, str(b.get("rate","0")))
        self.e_adv.insert(0, str(b.get("advance","0")))
        self.e_notes.insert("1.0", b.get("notes",""))

    def _collect(self):
        raw_date = self.e_date.get().strip()
        iso_date = raw_date
        try:
            d, m, y  = raw_date.split("/")
            iso_date = f"{int(y):04d}-{int(m):02d}-{int(d):02d}"
        except: pass
        return {
            "customer_name": self.e_name.get().strip(),
            "cnic":          self.e_cnic.get().strip(),
            "phone":         self.e_phone.get().strip(),
            "home_address":  self.e_addr.get().strip(),
            "event_date":    iso_date,
            "shift":         self.e_shift.get(),
            "persons":       self.e_pers.get().strip() or "0",
            "event_type":    self.e_evt.get(),
            "menu_type":     self.e_menu.get(),
            "filer_status":  self.e_filer.get(),
            "rate":          self.e_rate.get().strip() or "0",
            "advance":       self.e_adv.get().strip() or "0",
            "notes":         self.e_notes.get("1.0","end").strip(),
        }

    def _submit(self):
        d = self._collect()
        if not d["customer_name"]:
            self.st_var.set("Customer name is required."); return
        if not d["event_date"]:
            self.st_var.set("Event date is required."); return
        try:
            datetime.date.fromisoformat(d["event_date"])
        except ValueError:
            self.st_var.set("Invalid date. Use the calendar picker or DD/MM/YYYY."); return

        if self.existing:
            self.db.update(self.existing["id"], d)
            msg = f"Booking #{self.existing['id']} updated."
            self.on_done(self.existing["id"], msg)
        else:
            bid, msg = self.db.add(d)
            if bid is None:
                self.st_var.set(msg); return
            self.on_done(bid, msg)
        self.destroy()

                                                                      
                                                    
                                                                      

class ReceiptDialog(ctk.CTkToplevel):
    """
    Shows both receipt types in a tabbed window:
      Tab 1 — 🧾 Booking Receipt  (thermal printer)
      Tab 2 — 💳 Final Clearance  (A4 inkjet/laser)
    """
    def __init__(self, parent, b: dict, gen: ReceiptGen, db: DB,
                 start_tab: str = "booking"):
        super().__init__(parent)
        self.b   = b
        self.gen = gen
        self.db  = db
        self.title(f"Receipts — Booking #{b['id']}  |  {b.get('customer_name','')}")
        self.geometry("660x760+300+60")   # fixed position so it never spawns off-screen
        self.minsize(580, 620)
        self.configure(fg_color=BG)
        self.resizable(True, True)
        self.after(50, self.lift)          # bring to front after Tk finishes laying out
        self.after(60, self.focus_force)   # keep focus so window is immediately usable
        self.grab_set()
        self._build(start_tab)

    def _build(self, start_tab):
                
        hdr = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=0, height=56)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        ctk.CTkLabel(hdr,
                     text=f"🧾  Booking #{self.b['id']}  —  {self.b.get('customer_name','')}",
                     font=ctk.CTkFont(family="Georgia", size=20, weight="bold"),
                     text_color=GOLD).pack(side="left", padx=20, pady=14)

                                       
        if self.b.get("tax_paid"):
            ctk.CTkLabel(hdr, text="  ✅ PAID IN FULL  ",
                         font=ctk.CTkFont(family="Georgia", size=17, weight="bold"),
                         fg_color="#065F46", text_color="white",
                         corner_radius=6).pack(side="right", padx=20, pady=14)

                     
        tab_row = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=0, height=44)
        tab_row.pack(fill="x")
        tab_row.pack_propagate(False)

        self.tab_booking_btn = ctk.CTkButton(
            tab_row, text="🧾  Booking Receipt  (Thermal Printer)",
            command=lambda: self._switch("booking"),
            width=280, height=36,
            fg_color=GOLD if start_tab=="booking" else CARD,
            hover_color=GOLD_H,
            text_color="#FFFFFF" if start_tab=="booking" else MUTED,
            font=ctk.CTkFont(family="Georgia", size=18, weight="bold"),
            corner_radius=0)
        self.tab_booking_btn.pack(side="left")

        self.tab_clear_btn = ctk.CTkButton(
            tab_row, text="💳  Final Clearance  (A4 Printer)",
            command=lambda: self._switch("clearance"),
            width=260, height=36,
            fg_color=GOLD if start_tab=="clearance" else CARD,
            hover_color=GOLD_H,
            text_color="#FFFFFF" if start_tab=="clearance" else MUTED,
            font=ctk.CTkFont(family="Georgia", size=18, weight="bold"),
            corner_radius=0)
        self.tab_clear_btn.pack(side="left")

                        
        self.frame_booking   = ctk.CTkFrame(self, fg_color="transparent")
        self.frame_clearance = ctk.CTkFrame(self, fg_color="transparent")

        self._build_booking_tab()
        self._build_clearance_tab()

        self._switch(start_tab)

                                                                        
    def _build_booking_tab(self):
        f = self.frame_booking

        desc = ctk.CTkFrame(f, fg_color=CARD2, corner_radius=8)
        desc.pack(fill="x", padx=16, pady=(10,6))
        ctk.CTkLabel(desc,
                     text="📌  Print this on your thermal printer immediately after confirming a booking.\n"
                          "   Gives the customer their copy + keeps office copy for your records.",
                     font=ctk.CTkFont(family="Georgia", size=16), text_color=MUTED,
                     justify="left").pack(anchor="w", padx=14, pady=8)

        box = ctk.CTkTextbox(f, font=ctk.CTkFont(family="Courier New", size=16),
                              fg_color="white", text_color="#111111",
                              border_color=BORDER, border_width=1,
                              wrap="none")
        box.pack(fill="both", expand=True, padx=16, pady=(0,8))
        box.insert("1.0", self.gen.thermal_booking_text(self.b))
        box.configure(state="disabled")
        self._booking_box = box

        br = ctk.CTkFrame(f, fg_color="transparent")
        br.pack(fill="x", padx=16, pady=(0,14))
        btn(br, "🖨️  Send to Thermal Printer", self._print_thermal,
            w=230, h=40, size=18).pack(side="left", padx=(0,8))
        btn(br, "Close", self.destroy, w=80, h=40, size=17,
            color=CARD, hcolor=CARD2, tcolor=MUTED).pack(side="left")
        self.booking_status = ctk.CTkLabel(br, text="",
                                            font=ctk.CTkFont(family="Georgia", size=16),
                                            text_color=GREEN)
        self.booking_status.pack(side="left", padx=10)

                                                                        
    def _build_clearance_tab(self):
        f = self.frame_clearance

        desc = ctk.CTkFrame(f, fg_color=CARD2, corner_radius=8)
        desc.pack(fill="x", padx=16, pady=(10,8))
        ctk.CTkLabel(desc,
                     text="📌  Print this on your A4 printer when the customer clears full payment.\n"
                          "   This is the official proof of payment document.",
                     font=ctk.CTkFont(family="Georgia", size=16), text_color=MUTED,
                     justify="left").pack(anchor="w", padx=14, pady=8)

                                 
        pay_frame = ctk.CTkFrame(f, fg_color=BG, corner_radius=12)
        pay_frame.pack(fill="x", padx=16, pady=(0,8))

        gross_total = (self.b.get("persons",0) or 0) * (self.b.get("rate",0) or 0)
        saved_disc  = float(self.b.get("discount",0) or 0)
        saved_surp  = float(self.b.get("surplus",0) or 0)
        net_total   = max(0.0, gross_total - saved_disc + saved_surp)
        advance     = float(self.b.get("advance",0) or 0)
        fp_done     = float(self.b.get("final_payment",0) or 0)
        rem         = max(0, net_total - advance - fp_done)

        ctk.CTkLabel(pay_frame, text="💳  Record Final Payment",
                     font=ctk.CTkFont(family="Georgia", size=19, weight="bold"),
                     text_color=GOLD).pack(anchor="w", padx=16, pady=(12,6))

                     
        summary_row = ctk.CTkFrame(pay_frame, fg_color="transparent")
        summary_row.pack(fill="x", padx=16, pady=(0,8))
        for lbl, val, color in [
            ("Gross Total", f"Rs. {int(gross_total):,}", WHITE),
            ("Advance Paid", f"Rs. {int(advance):,}", GREEN),
            ("Balance Due", f"Rs. {int(rem):,}", ORANGE if rem > 0 else GREEN),
        ]:
            card = ctk.CTkFrame(summary_row, fg_color=CARD2, corner_radius=8, width=130, height=54)
            card.pack(side="left", padx=(0,8))
            card.pack_propagate(False)
            ctk.CTkLabel(card, text=val,
                         font=ctk.CTkFont(family="Georgia", size=18, weight="bold"),
                         text_color=color).pack(pady=(8,0))
            ctk.CTkLabel(card, text=lbl,
                         font=ctk.CTkFont(family="Georgia", size=15), text_color=MUTED).pack()

                             
        input_row = ctk.CTkFrame(pay_frame, fg_color="transparent")
        input_row.pack(fill="x", padx=16, pady=(4,6))
        ctk.CTkLabel(input_row, text="Final Payment Received (Rs.):",
                     font=ctk.CTkFont(family="Georgia", size=18), text_color=WHITE).pack(side="left", padx=(0,10))
        self.final_pay_entry = entry(input_row, f"{int(rem)}", 160)
        self.final_pay_entry.pack(side="left")
        self.final_pay_entry.insert(0, str(int(rem)))
        # Note: rem is already discount-aware via gross_total - saved_disc - advance

        # ── Discount field ─────────────────────────────────────────────
        disc_row = ctk.CTkFrame(pay_frame, fg_color="transparent")
        disc_row.pack(fill="x", padx=16, pady=(0,6))
        ctk.CTkLabel(disc_row, text="Discount Given   (Rs.):",
                     font=ctk.CTkFont(family="Georgia", size=18), text_color=ORANGE).pack(side="left", padx=(0,10))
        self.discount_entry = entry(disc_row, "0", 160)
        self.discount_entry.pack(side="left")
        self.discount_entry.insert(0, "0")
        ctk.CTkLabel(disc_row, text="  (0 = no discount)",
                     font=ctk.CTkFont(family="Georgia", size=15), text_color=MUTED).pack(side="left", padx=6)

        # ── Surplus / seating charge field ──────────────────────────────
        surp_row = ctk.CTkFrame(pay_frame, fg_color="transparent")
        surp_row.pack(fill="x", padx=16, pady=(0,14))
        ctk.CTkLabel(surp_row, text="Surplus Charge   (Rs.):",
                     font=ctk.CTkFont(family="Georgia", size=18), text_color=BLUE).pack(side="left", padx=(0,10))
        self.surplus_entry = entry(surp_row, "0", 160)
        self.surplus_entry.pack(side="left")
        self.surplus_entry.insert(0, "0")
        ctk.CTkLabel(surp_row, text="  (seating/extra — 0 if none)",
                     font=ctk.CTkFont(family="Georgia", size=15), text_color=MUTED).pack(side="left", padx=6)

                                                 
        if self.b.get("tax_paid") and self.b.get("final_payment"):
            self.final_pay_entry.delete(0, "end")
            self.final_pay_entry.insert(0, str(int(self.b.get("final_payment",0))))
            self.final_pay_entry.configure(state="disabled")
            saved_disc = float(self.b.get("discount", 0) or 0)
            self.discount_entry.delete(0, "end")
            self.discount_entry.insert(0, str(int(saved_disc)))
            self.discount_entry.configure(state="disabled")
            saved_surp = float(self.b.get("surplus", 0) or 0)
            self.surplus_entry.delete(0, "end")
            self.surplus_entry.insert(0, str(int(saved_surp)))
            self.surplus_entry.configure(state="disabled")

                 
        self.clear_box = ctk.CTkTextbox(f, font=ctk.CTkFont(family="Courier New", size=15),
                                         fg_color="white", text_color="#111111",
                                         border_color=BORDER, border_width=1,
                                         wrap="none", height=200)
        self.clear_box.pack(fill="both", expand=True, padx=16, pady=(0,8))
        self._update_clearance_preview()
        self.final_pay_entry.bind("<KeyRelease>", lambda e: self._update_clearance_preview())
        self.discount_entry.bind("<KeyRelease>", lambda e: self._update_clearance_preview())
        self.surplus_entry.bind("<KeyRelease>",  lambda e: self._update_clearance_preview())

                 
        br = ctk.CTkFrame(f, fg_color="transparent")
        br.pack(fill="x", padx=16, pady=(0,14))

        btn(br, "💳  Mark Paid & Save",
            self._mark_paid, w=180, h=40, size=18,
            color="#16A34A", hcolor="#15803D", tcolor="#FFFFFF").pack(side="left", padx=(0,8))
        btn(br, "📄  Print PDF (A4)",
            self._print_clearance_pdf, w=170, h=40, size=18).pack(side="left", padx=(0,8))
        btn(br, "🌐  Print via Browser",
            self._print_clearance_html, w=175, h=40, size=17,
            color=CARD, hcolor=CARD2, tcolor=WHITE).pack(side="left", padx=(0,8))
        btn(br, "Close", self.destroy, w=80, h=40, size=17,
            color=CARD, hcolor=CARD2, tcolor=MUTED).pack(side="left")

        self.clear_status = ctk.CTkLabel(br, text="",
                                          font=ctk.CTkFont(family="Georgia", size=16),
                                          text_color=GREEN, wraplength=300)
        self.clear_status.pack(side="left", padx=10)

                                                                         
    def _switch(self, tab):
        self.frame_booking.pack_forget()
        self.frame_clearance.pack_forget()
        if tab == "booking":
            self.frame_booking.pack(fill="both", expand=True)
            self.tab_booking_btn.configure(fg_color=GOLD, text_color="#FFFFFF")
            self.tab_clear_btn.configure(fg_color=CARD, text_color=MUTED)
        else:
            self.frame_clearance.pack(fill="both", expand=True)
            self.tab_clear_btn.configure(fg_color=GOLD, text_color="#FFFFFF")
            self.tab_booking_btn.configure(fg_color=CARD, text_color=MUTED)

                                                                         
    def _get_final_pay(self) -> float:
        try:    return max(0.0, float(self.final_pay_entry.get().strip() or 0))
        except: return 0.0

    def _get_discount(self) -> float:
        try:    return max(0.0, float(self.discount_entry.get().strip() or 0))
        except: return 0.0

    def _get_surplus(self) -> float:
        try:    return max(0.0, float(self.surplus_entry.get().strip() or 0))
        except: return 0.0

    def _update_clearance_preview(self):
        fp   = self._get_final_pay()
        disc = self._get_discount()
        surp = self._get_surplus()
        now  = datetime.datetime.now().strftime("%d-%b-%Y %I:%M %p")
        txt  = self.gen.clearance_text(self.b, fp, now, discount=disc, surplus=surp)
        self.clear_box.configure(state="normal")
        self.clear_box.delete("1.0", "end")
        self.clear_box.insert("1.0", txt)
        self.clear_box.configure(state="disabled")

    def _open_file(self, path):
        try:
            if sys.platform == "win32": os.startfile(path)
            else: subprocess.Popen(["xdg-open", path])
        except: pass

                                                                         
    def _print_thermal(self):
        """
        Print Customer Copy immediately, then Office Copy 2 seconds later —
        both silently to the configured thermal printer via SumatraPDF.
        Falls back to browser if SumatraPDF / printer not configured.
        """
        import webbrowser
        os.makedirs(RECEIPTS_DIR, exist_ok=True)
        bid = self.b["id"]

        # Write both HTML files
        cust_path = os.path.join(RECEIPTS_DIR, f"receipt_{bid}_customer.html")
        off_path  = os.path.join(RECEIPTS_DIR, f"receipt_{bid}_office.html")
        with open(cust_path, "w", encoding="utf-8") as fp:
            fp.write(self.gen.thermal_customer_html(self.b))
        with open(off_path, "w", encoding="utf-8") as fp:
            fp.write(self.gen.thermal_office_html(self.b))
        # Also save plain text record
        txt_path = os.path.join(RECEIPTS_DIR, f"booking_receipt_{bid}.txt")
        with open(txt_path, "w", encoding="utf-8") as fp:
            fp.write(self.gen.thermal_booking_text(self.b))

        printer  = self.gen._get_printer("thermal_printer")
        sumatra  = self.gen._find_sumatra()

        if sumatra and printer:
            # Silent path — both prints via SumatraPDF, 2-second gap
            ok1 = self.gen._silent_print_html(cust_path, printer, delay_ms=0)
            ok2 = self.gen._silent_print_html(off_path,  printer, delay_ms=2000)
            if ok1 and ok2:
                self.booking_status.configure(
                    text=f"✅ Customer copy sent now, Office copy in 2 s → {printer}",
                    text_color=GREEN)
                return

        # Browser fallback — open customer copy, then office copy after 2 s
        try:
            def _abs(p):
                return "file:///" + os.path.abspath(p).replace("\\", "/")
            webbrowser.open(_abs(cust_path))
            def _open_office():
                import time; time.sleep(2)
                webbrowser.open(_abs(off_path))
            threading.Thread(target=_open_office, daemon=True).start()
            tip = "  → Select thermal printer, 80mm paper."
            if sumatra and not printer:
                tip = "  ℹ️  Set Thermal Printer Name in Settings for silent printing."
            elif not sumatra:
                tip = "  ℹ️  Install SumatraPDF for one-click silent printing."
            self.booking_status.configure(
                text="✅ Customer copy opened. Office copy opens in 2 s.\n" + tip,
                text_color=GREEN)
        except Exception as e:
            self.booking_status.configure(text=f"Error: {e}", text_color=RED)

                                                                          
    def _mark_paid(self):
        if self.b.get("tax_paid"):
            self.clear_status.configure(
                text="Already marked as paid.", text_color=ORANGE); return
        fp   = self._get_final_pay()
        disc = self._get_discount()
        surp = self._get_surplus()
        cleared_at = self.db.mark_cleared(self.b["id"], fp, discount=disc, surplus=surp)
        self.b["tax_paid"]      = 1
        self.b["final_payment"] = fp
        self.b["cleared_at"]    = cleared_at
        self.b["discount"]      = disc
        self.b["surplus"]       = surp
        self.final_pay_entry.configure(state="disabled")
        self.discount_entry.configure(state="disabled")
        self.surplus_entry.configure(state="disabled")
        self.clear_status.configure(
            text=f"✅ Marked as PAID — Rs.{int(fp):,} received on {cleared_at}",
            text_color=GREEN)
                                        
        try:
            for w in self.winfo_children():
                if isinstance(w, ctk.CTkFrame):
                    for c in w.winfo_children():
                        if isinstance(c, ctk.CTkLabel) and "PAID IN FULL" in (c.cget("text") or ""):
                            return
        except: pass

    def _print_clearance_pdf(self):
        if not PDF_OK:
            self.clear_status.configure(
                text="reportlab not installed. Run: pip install reportlab",
                text_color=ORANGE); return
        os.makedirs(RECEIPTS_DIR, exist_ok=True)
        fp         = self._get_final_pay()
        disc       = self._get_discount()
        surp       = self._get_surplus()
        cleared_at = (self.b.get("cleared_at") or
                      datetime.datetime.now().strftime("%d-%b-%Y %I:%M %p"))
        path = os.path.join(RECEIPTS_DIR,
                            f"clearance_{self.b['id']}_{self.b.get('customer_name','').replace(' ','_')}.pdf")
        ok = self.gen.save_clearance_pdf(self.b, fp, cleared_at, path, discount=disc, surplus=surp)
        if ok:
            self.clear_status.configure(text=f"✅ PDF saved → {path}", text_color=GREEN)
            # Open PDF – user can print from the PDF viewer (proper paper size, margins etc.)
            self._open_file(path)
        else:
            # Fallback: open HTML version in browser
            self.clear_status.configure(
                text="PDF generation failed – opening browser version instead.",
                text_color=ORANGE)
            self._print_clearance_html()

    def _print_clearance_text(self):
        """Now opens A4 HTML in browser instead of Notepad.
        Browser print dialog gives proper A4 paper size selection."""
        self._print_clearance_html()

    def _print_clearance_html(self):
        """
        Send A4 clearance receipt to the configured A4 printer silently,
        or open browser print dialog if no printer is set.
        """
        import webbrowser
        os.makedirs(RECEIPTS_DIR, exist_ok=True)
        fp         = self._get_final_pay()
        disc       = self._get_discount()
        surp       = self._get_surplus()
        cleared_at = (self.b.get("cleared_at") or
                      datetime.datetime.now().strftime("%d-%b-%Y %I:%M %p"))
        txt_path  = os.path.join(RECEIPTS_DIR, f"clearance_{self.b['id']}.txt")
        html_path = os.path.join(RECEIPTS_DIR, f"clearance_{self.b['id']}.html")
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(self.gen.clearance_text(self.b, fp, cleared_at, discount=disc, surplus=surp))
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(self.gen.clearance_html(self.b, fp, cleared_at, discount=disc, surplus=surp))
        try:
            printer = self.gen._get_printer("a4_printer")
            if self.gen._silent_print_html(html_path, printer):
                self.clear_status.configure(
                    text=f"✅ Sent to A4 printer: {printer}",
                    text_color=GREEN)
            else:
                abs_path = os.path.abspath(html_path).replace("\\", "/")
                webbrowser.open(f"file:///{abs_path}")
                tip = ("  → Select your A4 printer, paper size A4." if not printer
                       else "  ℹ️  SumatraPDF not found — using browser dialog.")
                self.clear_status.configure(
                    text="✅ Browser print dialog opened.\n" + tip,
                    text_color=GREEN)
        except Exception as e:
            self.clear_status.configure(text=f"Error: {e}", text_color=RED)

                                                                      
                
                                                                      

class BookingsTab(ctk.CTkFrame):
    def __init__(self, parent, db: DB, gen: ReceiptGen, on_change=None):
        super().__init__(parent, fg_color="transparent")
        self.db        = db
        self.gen       = gen
        self.on_change = on_change
        self._build()
        self.refresh()

    def _build(self):
                        
        top = ctk.CTkFrame(self, bg_color=BG, fg_color=CARD, corner_radius=12,
                           border_width=2, border_color=BORDER)
        top.pack(fill="x", pady=(0,10))

        btn(top, "➕  New Booking",  self._new,       w=160, h=38).pack(side="left", padx=10, pady=10)
        btn(top, "✏️  Edit",          self._edit,      w=100, h=38).pack(side="left", padx=(0,6), pady=10)
        btn(top, "🧾  Receipt",       self._receipt,   w=110, h=38).pack(side="left", padx=(0,6), pady=10)
        btn(top, "💳  Clearance",     self._clearance, w=120, h=38,
            color="#16A34A", hcolor="#15803D", tcolor="#FFFFFF").pack(side="left", padx=(0,6), pady=10)
        btn(top, "❌  Cancel",        self._cancel,    w=100, h=38,
            color=RED, hcolor="#C0392B", tcolor=WHITE).pack(side="left", padx=(0,6), pady=10)
        btn(top, "🔄  Refresh",       self.refresh,    w=110, h=38,
            color=CARD, hcolor=CARD2, tcolor=MUTED).pack(side="left", padx=(0,6), pady=10)

                
        se = ctk.CTkFrame(top, fg_color="transparent")
        se.pack(side="right", padx=10, pady=10)
        self.q_entry = entry(se, "🔍  Search name / CNIC / phone / ID…", 300)
        self.q_entry.pack(side="left", padx=(0,6))
        self.q_entry.bind("<Return>",    lambda e: self._search())
        self.q_entry.bind("<KeyRelease>", lambda e: self._search())
        btn(se, "✕", self.refresh, w=36, h=36, size=18,
            color=CARD, hcolor=CARD2, tcolor=MUTED).pack(side="left")

              
        tree_frame = ctk.CTkFrame(self, bg_color=BG, fg_color=CARD, corner_radius=12,
                                  border_width=2, border_color=BORDER)
        tree_frame.pack(fill="both", expand=True)

        cols  = ("ID","Name","Date","Shift","Event","Persons","Total","Advance","Remaining","Status")
        wids  = (45, 150, 90, 55, 90, 65, 90, 85, 85, 75)
        self.tv = tree_setup(tree_frame, cols, wids)
        self.tv.bind("<Double-1>", lambda e: self._edit())

    def _row_vals(self, b):
        total  = (b.get("persons",0) or 0) * (b.get("rate",0) or 0)
        adv    = float(b.get("advance",0) or 0)
        fp     = float(b.get("final_payment",0) or 0)
        rem    = max(0, total - adv - fp)
        status = "✅ CLEARED" if b.get("tax_paid") else ("⚠️ Balance" if rem > 0 else "—")
        return (
            f"#{b['id']}", b["customer_name"], b["event_date"],
            b["shift"], b.get("event_type",""),
            b.get("persons",""),
            f"Rs.{int(total):,}", f"Rs.{int(adv):,}",
            f"Rs.{int(rem):,}", status
        )

    def refresh(self):
        self.q_entry.delete(0, "end")
        self._load(self.db.recent(50))

    def _load(self, rows):
        for i in self.tv.get_children(): self.tv.delete(i)
        for b in rows:
            vals = self._row_vals(b)
            # tag entire row for status-based coloring
            total  = (b.get("persons",0) or 0) * (b.get("rate",0) or 0)
            adv    = float(b.get("advance",0) or 0)
            fp     = float(b.get("final_payment",0) or 0)
            rem    = max(0, total - adv - fp)
            if b.get("is_cancelled"):
                tag = "status_cancelled"
            elif b.get("tax_paid"):
                tag = "status_cleared"
            elif rem > 0:
                tag = "status_pending"
            else:
                tag = "status_neutral"
            self.tv.insert("", "end", iid=str(b["id"]), values=vals, tags=(tag,))

    def _search(self):
        q = self.q_entry.get().strip()
        if q: self._load(self.db.search(q))
        else: self.refresh()

    def _selected_id(self):
        sel = self.tv.selection()
        if not sel:
            messagebox.showinfo("No selection", "Please select a booking first.")
            return None
        return int(sel[0])

    def _new(self):
        def done(bid, msg):
            messagebox.showinfo("Booking Confirmed", msg)
            self.refresh()
            if self.on_change: self.on_change()
                                                            
            b = self.db.get(bid)
            if b: ReceiptDialog(self, b, self.gen, self.db, start_tab="booking")
        BookingDialog(self, self.db, done)

    def _edit(self):
        bid = self._selected_id()
        if not bid: return
        b = self.db.get(bid)
        if not b: return
        def done(bid2, msg):
            messagebox.showinfo("Updated", msg)
            self.refresh()
            if self.on_change: self.on_change()
        BookingDialog(self, self.db, done, existing=b)

    def _receipt(self):
        """Open receipts window on Booking Receipt tab."""
        bid = self._selected_id()
        if not bid: return
        b = self.db.get(bid)
        if b: ReceiptDialog(self, b, self.gen, self.db, start_tab="booking")

    def _clearance(self):
        """Open receipts window directly on Final Clearance tab."""
        bid = self._selected_id()
        if not bid: return
        b = self.db.get(bid)
        if b: ReceiptDialog(self, b, self.gen, self.db, start_tab="clearance")

    def _cancel(self):
        bid = self._selected_id()
        if not bid: return
        b = self.db.get(bid)
        if not b: return
        if messagebox.askyesno("Cancel Booking",
                                f"Cancel booking #{bid} for {b['customer_name']}?\n"
                                "This is recorded in the audit log (PRA-compliant)."):
            self.db.cancel(bid, "Cancelled by operator")
            self.refresh()
            if self.on_change: self.on_change()
            messagebox.showinfo("Done", f"Booking #{bid} cancelled.")

                                                                      
                       
                                                                      

class VoiceTab(ctk.CTkFrame):
    def __init__(self, parent, voice: Voice):
        super().__init__(parent, fg_color="transparent")
        self.voice      = voice
        self.listening  = False
        self._build()

    def _build(self):
        center = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=16,
                              border_width=1, border_color=BORDER)
        center.pack(expand=True, fill="both", padx=30, pady=20)

        ctk.CTkLabel(center, text="🎙️  Voice Assistant",
                     font=ctk.CTkFont(family="Georgia", size=28, weight="bold"),
                     text_color=GOLD).pack(pady=(24,4))
        ctk.CTkLabel(center,
                     text="Check hall availability in English, Urdu, or mixed",
                     font=ctk.CTkFont(family="Georgia", size=18), text_color=MUTED).pack(pady=(0,20))

                     
        ex_frame = ctk.CTkFrame(center, fg_color=CARD2, corner_radius=12,
                                border_width=1, border_color=BORDER)
        ex_frame.pack(padx=40, pady=(0,20), fill="x")
        ctk.CTkLabel(ex_frame, text="Ask about a specific date or a full month. "
                     "Mention Day / Night shift if needed.",
                     font=ctk.CTkFont(family="Georgia", size=17), text_color=MUTED,
                     wraplength=480, justify="left").pack(padx=16, pady=12)

                    
        self.mic = ctk.CTkButton(
            center, text="🎙️  TAP TO SPEAK",
            command=self._toggle,
            width=230, height=72,
            fg_color=GOLD, hover_color=GOLD_H,
            text_color="#FFFFFF",
            font=ctk.CTkFont(family="Georgia", size=23, weight="bold"),
            corner_radius=40)
        self.mic.pack(pady=16)

        self.st_var = ctk.StringVar(value="Ready — tap the mic or type below")
        ctk.CTkLabel(center, textvariable=self.st_var,
                     font=ctk.CTkFont(family="Georgia", size=17), text_color=MUTED).pack(pady=4)

                              
        for attr, lbl_text in [("heard_var","Heard:"),("result_var","Result:")]:
            f = ctk.CTkFrame(center, fg_color=BG, corner_radius=12)
            f.pack(fill="x", padx=40, pady=8)
            ctk.CTkLabel(f, text=lbl_text, font=ctk.CTkFont(family="Georgia", size=16),
                         text_color=MUTED).pack(anchor="w", padx=12, pady=(8,0))
            v = ctk.StringVar(value="—")
            setattr(self, attr, v)
            lbl = ctk.CTkLabel(f, textvariable=v,
                               font=ctk.CTkFont(family="Georgia", size=19, weight="bold"),
                               text_color=GREEN, wraplength=500)
            lbl.pack(anchor="w", padx=12, pady=(0,10))
            if attr == "result_var":
                self.result_lbl = lbl

                      
        ctk.CTkFrame(center, height=1, fg_color=GOLD_DK).pack(fill="x", padx=40, pady=4)
        ctk.CTkLabel(center, text="Or type your question:",
                     font=ctk.CTkFont(family="Georgia", size=17), text_color=MUTED).pack(pady=(8,4))
        mr = ctk.CTkFrame(center, fg_color="transparent")
        mr.pack(padx=40, pady=(0,24), fill="x")
        self.manual = entry(mr, "e.g. 15 March available hai?", 380)
        self.manual.pack(side="left", expand=True, fill="x", padx=(0,10))
        btn(mr, "Ask", self._manual_ask, w=80, h=36, size=18).pack(side="left")
        self.manual.bind("<Return>", lambda e: self._manual_ask())

    def _toggle(self):
        if self.listening: return
        self.mic.configure(state="disabled")
        threading.Thread(target=self._listen_thread, daemon=True).start()

    def _listen_thread(self):
        self.listening = True
        self.after(0, lambda: self.mic.configure(
            fg_color=RED, hover_color="#C0392B", text="🔴  LISTENING...", state="normal"))
        self.after(0, lambda: self.st_var.set("🔴 Listening..."))
        try:
            text = self.voice.listen()
            self.after(0, lambda t=text: self.heard_var.set(f'"{t}"'))
            self.after(0, lambda: self.st_var.set("⚙️ Asking Claude..."))
            resp = self.voice.handle(text)
            self.after(0, lambda r=resp: self._show(r))
            self.voice.speak(resp)
        except Exception as e:
            err = str(e)
            msg = ("No speech detected — please try again."
                   if "timeout" in err.lower() or "WaitTimeout" in err
                   else f"Error: {err}")
            self.after(0, lambda m=msg: self._show(m, err=True))
        finally:
            self.listening = False
            self.after(0, lambda: self.mic.configure(
                fg_color=GOLD, hover_color=GOLD_H,
                text="🎙️  TAP TO SPEAK", state="normal"))
            self.after(0, lambda: self.st_var.set("Ready — tap the mic or type below"))

    def _manual_ask(self):
        text = self.manual.get().strip()
        if not text: return
        self.heard_var.set(f'"{text}"')
        self.st_var.set("⚙️ Asking Claude...")
        self.manual.delete(0, "end")
        def _go():
            try:
                resp = self.voice.handle(text)
                self.after(0, lambda r=resp: self._show(r))
                self.after(0, lambda: self.voice.speak(resp))
            except Exception as e:
                self.after(0, lambda m=str(e): self._show(f"Error: {m}", err=True))
            finally:
                self.after(0, lambda: self.st_var.set("Ready — tap the mic or type below"))
        threading.Thread(target=_go, daemon=True).start()

    def _show(self, text, err=False):
        self.result_var.set(text)
        if err: color = RED
        elif any(w in text.lower() for w in ["fully booked","both shift","taken"]):
            color = RED
        elif any(w in text.lower() for w in ["day taken","night taken","one shift"]):
            color = ORANGE
        else:
            color = GREEN
        self.result_lbl.configure(text_color=color)

                                                                      
                
                                                                      

class CalendarTab(ctk.CTkFrame):
    def __init__(self, parent, db: DB):
        super().__init__(parent, fg_color="transparent")
        self.db   = db
        today     = datetime.date.today()
        self.year  = today.year
        self.month = today.month
        self._build()
        self.draw()

    def _build(self):
        nav = ctk.CTkFrame(self, fg_color=BG, corner_radius=12)
        nav.pack(fill="x", pady=(0,12))

        btn(nav, "◀", self._prev, w=38, h=36, size=19,
            color=GOLD, hcolor=GOLD_H, tcolor="#1E1B10").pack(side="left", padx=8, pady=8)

        self.month_var = ctk.StringVar(value=MONTHS[self.month-1])
        ctk.CTkOptionMenu(
            nav, variable=self.month_var, values=MONTHS,
            width=130, height=36, fg_color=CARD, button_color=GOLD_DK,
            text_color=WHITE, dropdown_fg_color=PANEL, dropdown_hover_color=GOLD_DK,
            font=ctk.CTkFont(family="Georgia", size=19, weight="bold"),
            command=self._on_month_change
        ).pack(side="left", padx=6, pady=8)

        self.year_var = ctk.StringVar(value=str(self.year))
        ye = ctk.CTkEntry(nav, textvariable=self.year_var, width=72, height=36,
                          fg_color=CARD, border_color=BORDER, text_color=WHITE,
                          font=ctk.CTkFont(family="Georgia", size=19, weight="bold"), justify="center")
        ye.pack(side="left", padx=6, pady=8)
        ye.bind("<Return>",   self._on_year_change)
        ye.bind("<FocusOut>", self._on_year_change)

        btn(nav, "▶", self._next, w=38, h=36, size=19,
            color=GOLD, hcolor=GOLD_H, tcolor="#1E1B10").pack(side="left", padx=8, pady=8)

        btn(nav, "Today", self._goto_today, w=70, h=36, size=17,
            color=GOLD_DK, hcolor=GOLD, tcolor="#1E1B10").pack(side="left", padx=(0,8), pady=8)

        leg = ctk.CTkFrame(nav, fg_color="transparent")
        leg.pack(side="right", padx=12)
        ctk.CTkFrame(leg, width=14, height=14, fg_color=GOLD_DK, corner_radius=4).pack(side="left", padx=(10,4))
        ctk.CTkLabel(leg, text="Booked", font=ctk.CTkFont(family="Georgia", size=16), text_color=MUTED).pack(side="left", padx=(0,12))
        ctk.CTkFrame(leg, width=14, height=14, fg_color=BORDER, corner_radius=4).pack(side="left", padx=(0,4))
        ctk.CTkLabel(leg, text="Free", font=ctk.CTkFont(family="Georgia", size=16), text_color=MUTED).pack(side="left", padx=(0,4))
        ctk.CTkLabel(leg, text="  Layout: Mo Af / Ev Ni", font=ctk.CTkFont(family="Georgia", size=14), text_color=MUTED).pack(side="left", padx=(8,0))

        self.grid_frame = ctk.CTkFrame(self, fg_color=BG, corner_radius=12)
        self.grid_frame.pack(fill="both", expand=True)

    def _on_month_change(self, val):
        self.month = MONTHS.index(val) + 1
        self.draw()

    def _on_year_change(self, event=None):
        try:
            self.year = int(self.year_var.get())
            self.draw()
        except: pass

    def _goto_today(self):
        today = datetime.date.today()
        self.year, self.month = today.year, today.month
        self.month_var.set(MONTHS[self.month-1])
        self.year_var.set(str(self.year))
        self.draw()

    def _prev(self):
        self.month -= 1
        if self.month < 1: self.month = 12; self.year -= 1
        self.month_var.set(MONTHS[self.month-1])
        self.year_var.set(str(self.year))
        self.draw()

    def _next(self):
        self.month += 1
        if self.month > 12: self.month = 1; self.year += 1
        self.month_var.set(MONTHS[self.month-1])
        self.year_var.set(str(self.year))
        self.draw()

    def draw(self):
        for w in self.grid_frame.winfo_children(): w.destroy()
        y, m   = self.year, self.month
        amap   = self.db.month_avail(y, m)
        first, total = calendar.monthrange(y, m)
        today  = datetime.date.today()

        for ci, d in enumerate(["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]):
            ctk.CTkLabel(self.grid_frame, text=d,
                         font=ctk.CTkFont(family="Georgia", size=18, weight="bold"),
                         text_color=GOLD, width=90, height=32
                         ).grid(row=0, column=ci, padx=3, pady=(12,4))

        # Single warm-gold colour for booked shifts, BORDER for free.
        # 2×2 grid inside each cell: top-left=Morning, top-right=Afternoon,
        #                             bot-left=Evening, bot-right=Night
        SLOT_GRID = [
            ("Morning",   0, 0),
            ("Afternoon", 0, 1),
            ("Evening",   1, 0),
            ("Night",     1, 1),
        ]
        SLOT_ABBR = {"Morning":"Mo","Afternoon":"Af","Evening":"Ev","Night":"Ni"}
        BOOKED_COLOR = GOLD_DK   # single colour for all booked shifts
        FREE_COLOR   = CARD2     # soft grey for free shifts

        for day in range(1, total+1):
            taken    = set(amap.get(day, []))  # back to set for O(1) lookup
            is_today = datetime.date(y, m, day) == today

            cell = ctk.CTkFrame(self.grid_frame, fg_color=PANEL, corner_radius=10,
                                width=90, height=82,
                                border_color=GOLD, border_width=2 if is_today else 1)
            wd = (first + day - 1) % 7
            ro = 1 + (first + day - 1) // 7
            cell.grid(row=ro, column=wd, padx=3, pady=3, sticky="nsew")
            cell.grid_propagate(False)

            # ── Day number (top-left, small so the grid can breathe) ──────
            ctk.CTkLabel(cell, text=str(day),
                         font=ctk.CTkFont(family="Georgia", size=13, weight="bold"),
                         text_color=GOLD if is_today else WHITE,
                         fg_color="transparent").place(relx=0.05, rely=0.02)

            # ── 2×2 shift grid fills the lower 58% of the cell ───────────
            quad = ctk.CTkFrame(cell, fg_color="transparent")
            quad.place(relx=0.0, rely=0.36, relwidth=1.0, relheight=0.62)
            for slot, r_, c_ in SLOT_GRID:
                booked = slot in taken
                bg     = BOOKED_COLOR if booked else FREE_COLOR
                tc     = "#FFFFFF"    if booked else MUTED
                # Each quadrant fills half the quad frame
                q = ctk.CTkFrame(quad, fg_color=bg, corner_radius=0)
                q.grid(row=r_, column=c_, padx=1, pady=1, sticky="nsew")
                ctk.CTkLabel(q, text=SLOT_ABBR[slot],
                             font=ctk.CTkFont(family="Georgia", size=9),
                             text_color=tc,
                             fg_color="transparent").place(relx=0.5, rely=0.5, anchor="center")
            quad.grid_rowconfigure(0, weight=1)
            quad.grid_rowconfigure(1, weight=1)
            quad.grid_columnconfigure(0, weight=1)
            quad.grid_columnconfigure(1, weight=1)

        for ci in range(7):
            self.grid_frame.grid_columnconfigure(ci, weight=1)

                                                                      
               
                                                                      

class ReportsTab(ctk.CTkFrame):
    def __init__(self, parent, db: DB, gen: ReceiptGen, cfg: Config):
        super().__init__(parent, fg_color="transparent")
        self.db  = db
        self.gen = gen
        self.cfg = cfg
        self._build()

    def _build(self):
        left  = ctk.CTkFrame(self, fg_color=BG, corner_radius=12)
        left.pack(side="left", fill="y", padx=(0,10), pady=0)
        right = ctk.CTkFrame(self, fg_color=BG, corner_radius=12)
        right.pack(side="right", fill="both", expand=True)

                                                                      
        ctk.CTkLabel(left, text="📊  Reports",
                     font=ctk.CTkFont(family="Georgia", size=23, weight="bold"),
                     text_color=GOLD).pack(padx=20, pady=(20,16))

        today = datetime.date.today()

        fld_lbl(left, "Year").pack(anchor="w", padx=20)
        self.e_year = entry(left, str(today.year), 160)
        self.e_year.pack(padx=20, pady=(4,12))
        self.e_year.insert(0, str(today.year))

        fld_lbl(left, "Month").pack(anchor="w", padx=20)
        self.e_month = cbo(left, MONTHS, 160)
        self.e_month.pack(padx=20, pady=(4,12))
        self.e_month.set(MONTHS[today.month - 1])

        btn(left, "📋  Monthly Report",  self._monthly,  w=180, h=38).pack(padx=20, pady=6)
        btn(left, "📅  Yearly Overview", self._yearly,   w=180, h=38).pack(padx=20, pady=6)

        ctk.CTkFrame(left, height=1, fg_color=GOLD_DK).pack(fill="x", padx=20, pady=16)

        btn(left, "📄  Export PDF",   self._export_pdf, w=180, h=38).pack(padx=20, pady=6)
        btn(left, "💾  Backup DB",    self._backup,     w=180, h=38,
            color=BLUE, hcolor="#2563EB", tcolor=WHITE).pack(padx=20, pady=6)

        self.side_status = ctk.CTkLabel(left, text="",
                                         font=ctk.CTkFont(family="Georgia", size=16),
                                         text_color=GREEN, wraplength=180)
        self.side_status.pack(padx=20, pady=8)

                                                                      
                           
        self.cards_frame = ctk.CTkFrame(right, fg_color="transparent")
        self.cards_frame.pack(fill="x", padx=16, pady=16)

        self.report_title = ctk.CTkLabel(right, text="Select a report →",
                                          font=ctk.CTkFont(family="Georgia", size=20, weight="bold"),
                                          text_color=GOLD)
        self.report_title.pack(anchor="w", padx=16, pady=(0,8))

        tf = ctk.CTkFrame(right, fg_color=BG, corner_radius=12)
        tf.pack(fill="both", expand=True, padx=16, pady=(0,16))

        cols  = ("ID","Name","Date","Shift","Persons","Total","Advance","Remaining","PRA","FBR")
        wids  = (40, 130, 85, 55, 65, 80, 80, 80, 70, 70)
        self.tv = tree_setup(tf, cols, wids)

    def _card(self, label, value, color=GREEN):
        """Create a small summary stat card."""
        for w in self.cards_frame.winfo_children(): pass                         
        f = ctk.CTkFrame(self.cards_frame, fg_color=BG, corner_radius=12, width=140, height=70)
        f.pack(side="left", padx=6, pady=4)
        f.pack_propagate(False)
        ctk.CTkLabel(f, text=value,
                     font=ctk.CTkFont(family="Georgia", size=19, weight="bold"),
                     text_color=color).pack(pady=(10,2))
        ctk.CTkLabel(f, text=label,
                     font=ctk.CTkFont(family="Georgia", size=15),
                     text_color=MUTED).pack()

    def _clear_cards(self):
        for w in self.cards_frame.winfo_children(): w.destroy()

    def _load_table(self, rows):
        for i in self.tv.get_children(): self.tv.delete(i)
        for b in rows:
            total = (b.get("persons",0) or 0) * (b.get("rate",0) or 0)
            rem   = max(0, total - (b.get("advance",0) or 0) - (b.get("final_payment",0) or 0))
            self.tv.insert("", "end", values=(
                f"#{b['id']}", b["customer_name"], b["event_date"],
                b["shift"], b.get("persons",""),
                f"Rs.{int(total):,}", f"Rs.{int(b.get('advance',0) or 0):,}",
                f"Rs.{int(rem):,}",
                f"Rs.{int(b.get('pra_tax',0) or 0):,}",
                f"Rs.{int(b.get('fbr_tax',0) or 0):,}",
            ))

    def _monthly(self):
        try:
            yr = int(self.e_year.get())
            mn = MONTHS.index(self.e_month.get()) + 1
        except: return
        s = self.db.summary(yr, mn)
        self._clear_cards()
        self._card("Bookings",  str(s["count"]))
        self._card("Revenue",   f"Rs.{int(s['revenue']):,}", GOLD)
        self._card("Collected", f"Rs.{int(s['advance']):,}", GREEN)
        self._card("Remaining", f"Rs.{int(s['remaining']):,}", ORANGE)
        self._card("PRA Tax",   f"Rs.{int(s['pra_tax']):,}", BLUE)
        self._card("FBR Tax",   f"Rs.{int(s['fbr_tax']):,}", RED)
        self.report_title.configure(
            text=f"{MONTHS[mn-1]} {yr} — Monthly Report ({s['count']} bookings)")
        self._load_table(s["bookings"])

    def _yearly(self):
        try: yr = int(self.e_year.get())
        except: return
        data = self.db.yearly_monthly(yr)
        for i in self.tv.get_children(): self.tv.delete(i)
                                     
        self._clear_cards()
        total_rev = sum(d["revenue"] for d in data)
        total_cnt = sum(d["count"]   for d in data)
        self._card("Total Bookings", str(total_cnt))
        self._card("Total Revenue",  f"Rs.{int(total_rev):,}", GOLD)
        self.report_title.configure(text=f"Yearly Overview — {yr}")
                                      
        for i in self.tv.get_children(): self.tv.delete(i)
        for d in data:
            self.tv.insert("", "end", values=(
                "—", d["month"], f"{yr}", "—", str(d["count"]),
                f"Rs.{int(d['revenue']):,}",
                f"Rs.{int(d['advance']):,}",
                f"Rs.{int(d['remaining']):,}",
                f"Rs.{int(d['pra_tax']):,}",
                f"Rs.{int(d['fbr_tax']):,}",
            ))

    def _upcoming(self):
        rows = self.db.upcoming()
        self._clear_cards()
        self._card("Upcoming", str(len(rows)), GOLD)
        self.report_title.configure(text=f"Upcoming Bookings ({len(rows)} total)")
        self._load_table(rows)

    def _export_pdf(self):
        if not PDF_OK:
            self.side_status.configure(text="Install reportlab for PDF", text_color=ORANGE); return
        try:
            yr = int(self.e_year.get())
            mn = MONTHS.index(self.e_month.get()) + 1
        except: return
        s    = self.db.summary(yr, mn)
        name = f"report_{MONTHS[mn-1]}_{yr}.pdf"
        path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF","*.pdf")],
            initialfile=name)
        if not path: return
        self._generate_report_pdf(s, path, yr, mn)
        self.side_status.configure(text=f"✅ PDF saved", text_color=GREEN)
        if sys.platform == "win32": os.startfile(path)

    def _generate_report_pdf(self, s, path, year, month):
        if not PDF_OK: return
        doc  = SimpleDocTemplate(path, pagesize=A4,
                                  topMargin=1.5*cm, bottomMargin=1.5*cm,
                                  leftMargin=2*cm, rightMargin=2*cm)
        ss   = getSampleStyleSheet()
        gold = colors.HexColor(GOLD)
        story = []

        title_s = ParagraphStyle("t", parent=ss["Normal"],
                                  fontSize=20, textColor=gold,
                                  alignment=TA_CENTER, fontName="Helvetica-Bold")
        sub_s   = ParagraphStyle("s", parent=ss["Normal"],
                                  fontSize=11, textColor=colors.gray,
                                  alignment=TA_CENTER)
        story.append(Paragraph(self.cfg.get("hall_name","Dhanak Banquet Hall"), title_s))
        story.append(Paragraph(f"Monthly Report — {MONTHS[month-1]} {year}", sub_s))
        story.append(Spacer(1, 0.5*cm))

                       
        sum_data = [
            ["Total Bookings", str(s["count"])],
            ["Gross Revenue",  f"Rs. {int(s['revenue']):,}"],
            ["Advance Received",f"Rs. {int(s['advance']):,}"],
            ["Balance Remaining",f"Rs. {int(s['remaining']):,}"],
            ["PRA Tax (5%)",   f"Rs. {int(s['pra_tax']):,}"],
            ["FBR Tax",        f"Rs. {int(s['fbr_tax']):,}"],
        ]
        sum_tbl = Table(sum_data, colWidths=[9*cm, 6*cm])
        sum_tbl.setStyle(TableStyle([
            ("BACKGROUND",  (0,0),(1,0), gold),
            ("TEXTCOLOR",   (0,0),(1,0), colors.white),
            ("FONTSIZE",    (0,0),(-1,-1), 11),
            ("TOPPADDING",  (0,0),(-1,-1), 6),
            ("BOTTOMPADDING",(0,0),(-1,-1),6),
            ("LEFTPADDING", (0,0),(-1,-1), 10),
            ("ALIGN",       (1,0),(1,-1), "RIGHT"),
            ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white, colors.HexColor("#F9FAFB")]),
            ("LINEBELOW",   (0,-1),(1,-1), 1, gold),
        ]))
        story.append(sum_tbl)
        story.append(Spacer(1, 0.5*cm))

                        
        story.append(Paragraph("Booking Details", ParagraphStyle(
            "h2", parent=ss["Normal"], fontSize=13, textColor=gold,
            fontName="Helvetica-Bold", spaceBefore=8)))
        story.append(Spacer(1, 0.3*cm))

        hdr = [["#","Customer","Date","Shift","Persons","Total","Advance","PRA"]]
        bdata = hdr + [
            [f"#{b['id']}", b["customer_name"][:20], b["event_date"],
             b["shift"], str(b.get("persons",0)),
             f"Rs.{int((b.get('persons',0) or 0)*(b.get('rate',0) or 0)):,}",
             f"Rs.{int(b.get('advance',0) or 0):,}",
             f"Rs.{int(b.get('pra_tax',0) or 0):,}"]
            for b in s["bookings"]
        ]
        dtbl = Table(bdata, colWidths=[1.2*cm,4.5*cm,2.5*cm,1.8*cm,2*cm,2.5*cm,2.5*cm,2*cm])
        dtbl.setStyle(TableStyle([
            ("BACKGROUND",  (0,0),(-1,0), gold),
            ("TEXTCOLOR",   (0,0),(-1,0), colors.white),
            ("FONTNAME",    (0,0),(-1,0), "Helvetica-Bold"),
            ("FONTSIZE",    (0,0),(-1,-1), 9),
            ("TOPPADDING",  (0,0),(-1,-1), 4),
            ("BOTTOMPADDING",(0,0),(-1,-1),4),
            ("ALIGN",       (0,0),(-1,-1), "CENTER"),
            ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white, colors.HexColor("#F9FAFB")]),
            ("GRID",        (0,0),(-1,-1), 0.3, colors.lightgrey),
        ]))
        story.append(dtbl)
        doc.build(story)

    def _backup(self):
        try:
            path = self.db.backup()
            self.side_status.configure(text=f"✅ {os.path.basename(path)}", text_color=GREEN)
        except Exception as e:
            self.side_status.configure(text=f"Error: {e}", text_color=RED)

                                                                      
                
                                                                      

class SettingsTab(ctk.CTkFrame):
    def __init__(self, parent, cfg: Config, db: DB):
        super().__init__(parent, fg_color="transparent")
        self.cfg = cfg
        self.db  = db
        self._build()

    def _build(self):
        scroll = ctk.CTkScrollableFrame(self, fg_color=BG, corner_radius=0)
        scroll.pack(fill="both", expand=True)

        ctk.CTkLabel(scroll, text="⚙️  Settings",
                     font=ctk.CTkFont(family="Georgia", size=26, weight="bold"),
                     text_color=GOLD).pack(anchor="w", padx=24, pady=(20,16))

                                                                      
        # ── Appearance ────────────────────────────────────────────────────
        sec_lbl(scroll, "▸  APPEARANCE").pack(anchor="w", padx=24, pady=(8,4))
        ap_f = ctk.CTkFrame(scroll, fg_color=BG, corner_radius=12)
        ap_f.pack(fill="x", padx=24, pady=(4,16))
        ap_row = ctk.CTkFrame(ap_f, fg_color="transparent")
        ap_row.pack(fill="x", padx=16, pady=12)
        ctk.CTkLabel(ap_row, text="Dark Mode:",
                     font=ctk.CTkFont(family="Georgia", size=18), text_color=WHITE,
                     width=140, anchor="w").pack(side="left")
        self._dm_var = ctk.StringVar(value="dark" if self.cfg.get("dark_mode","0")=="1" else "light")
        self._dm_sw  = ctk.CTkSwitch(ap_row, text="",
                                      variable=self._dm_var, onvalue="dark", offvalue="light",
                                      command=self._toggle_dark,
                                      fg_color=BORDER, progress_color=GOLD)
        self._dm_sw.pack(side="left")
        ctk.CTkLabel(ap_row, text="Saved on next 'Save All Settings' and applied on restart.",
                     font=ctk.CTkFont(family="Georgia", size=14), text_color=MUTED).pack(side="left", padx=10)

        sec_lbl(scroll, "▸  CLAUDE AI — VOICE ASSISTANT").pack(anchor="w", padx=24, pady=(8,4))
        ai_f = ctk.CTkFrame(scroll, fg_color=BG, corner_radius=12)
        ai_f.pack(fill="x", padx=24, pady=(4,16))

        ctk.CTkLabel(ai_f,
                     text="Get free API key → console.anthropic.com → API Keys → Create Key",
                     font=ctk.CTkFont(family="Georgia", size=17), text_color=MUTED).pack(anchor="w", padx=16, pady=(12,4))
        kr = ctk.CTkFrame(ai_f, fg_color="transparent")
        kr.pack(fill="x", padx=16, pady=(0,4))
        ctk.CTkLabel(kr, text="API Key:", width=80,
                     font=ctk.CTkFont(family="Georgia", size=18), text_color=WHITE).pack(side="left")
        self.api_e = ctk.CTkEntry(kr, show="•", width=360, height=36,
                                   fg_color=CARD2, border_color=BORDER,
                                   text_color=WHITE, font=ctk.CTkFont(family="Georgia", size=18))
        self.api_e.pack(side="left", padx=8)
        self.api_e.insert(0, self.cfg.get("api_key"))

        ctk.CTkLabel(ai_f,
                     text="💡 Uses claude-haiku — ~Rs.0.30 per 1,000 queries. Almost free.",
                     font=ctk.CTkFont(family="Georgia", size=16, slant="italic"),
                     text_color=MUTED).pack(anchor="w", padx=16, pady=(0,12))

                                                                       
        sec_lbl(scroll, "▸  HALL INFORMATION (printed on receipts & PDFs)").pack(anchor="w", padx=24, pady=(8,4))
        hi_f = ctk.CTkFrame(scroll, fg_color=BG, corner_radius=12)
        hi_f.pack(fill="x", padx=24, pady=(4,16))

        fields = [("Hall Name","hall_name"),("Address","hall_address"),
                  ("Phone 1","hall_phone1"),("Phone 2","hall_phone2"),
                  ("NTN (optional)","hall_ntn"),("PRA STRN (optional)","hall_strn"),
                  ("Thermal Printer Name","thermal_printer"),("A4 Printer Name","a4_printer")]
        self.info_e = {}
        for lbl, key in fields:
            r = ctk.CTkFrame(hi_f, fg_color="transparent")
            r.pack(fill="x", padx=16, pady=4)
            ctk.CTkLabel(r, text=f"{lbl}:", width=140,
                         font=ctk.CTkFont(family="Georgia", size=18), text_color=MUTED, anchor="w").pack(side="left")
            e = entry(r, "", 300)
            e.insert(0, self.cfg.get(key))
            e.pack(side="left")
            self.info_e[key] = e
        ctk.CTkFrame(hi_f, height=8, fg_color="transparent").pack()

                                                                       
        sec_lbl(scroll, "▸  BACKUP & DATABASE").pack(anchor="w", padx=24, pady=(8,4))
        bk_f = ctk.CTkFrame(scroll, fg_color=BG, corner_radius=12)
        bk_f.pack(fill="x", padx=24, pady=(4,16))

        bk_r = ctk.CTkFrame(bk_f, fg_color="transparent")
        bk_r.pack(fill="x", padx=16, pady=12)
        btn(bk_r, "💾  Backup Now", self._backup, w=150, h=38).pack(side="left", padx=(0,12))
        btn(bk_r, "📁  Open Folder", self._open_folder, w=140, h=38,
            color=CARD2, hcolor=CARD, tcolor=WHITE).pack(side="left")
        self.bk_st = ctk.CTkLabel(bk_r, text="", font=ctk.CTkFont(family="Georgia", size=16), text_color=GREEN)
        self.bk_st.pack(side="left", padx=12)

        ctk.CTkLabel(bk_f,
                     text=f"DB file: {DB_FILE}    Backups: ./{BACKUP_DIR}/",
                     font=ctk.CTkFont(family="Georgia", size=16), text_color=MUTED).pack(anchor="w", padx=16, pady=(0,12))

                                                                        
        sec_lbl(scroll, "▸  GOOGLE SHEETS / CSV EXPORT").pack(anchor="w", padx=24, pady=(8,4))
        gs_f = ctk.CTkFrame(scroll, fg_color=BG, corner_radius=12,
                            border_width=1, border_color=BORDER)
        gs_f.pack(fill="x", padx=24, pady=(4,16))

        # ── OPTION A: One-click CSV → drag into Sheets (always works, no setup) ──
        opt_a = ctk.CTkFrame(gs_f, fg_color=CARD2, corner_radius=8)
        opt_a.pack(fill="x", padx=16, pady=(12,6))
        ctk.CTkLabel(opt_a, text="🚀  Option A — Instant CSV Export  (no setup needed)",
                     font=ctk.CTkFont(family="Georgia", size=16, weight="bold"),
                     text_color=GOLD).pack(anchor="w", padx=12, pady=(8,2))
        ctk.CTkLabel(opt_a,
                     text="Export all bookings as a .csv file → open Google Sheets → File → Import → Upload the CSV.\n"
                          "Takes 10 seconds. Works offline. No accounts, no API keys, no setup.",
                     font=ctk.CTkFont(family="Georgia", size=15), text_color=MUTED,
                     justify="left", wraplength=560).pack(anchor="w", padx=12, pady=(0,6))
        csv_btn_row = ctk.CTkFrame(opt_a, fg_color="transparent")
        csv_btn_row.pack(fill="x", padx=12, pady=(0,10))
        btn(csv_btn_row, "📥  Export CSV Now", self._export_csv,
            w=180, h=36, size=17).pack(side="left", padx=(0,10))
        btn(csv_btn_row, "📂  Open Exports Folder", self._open_exports_folder,
            w=190, h=36, size=16, color=CARD, hcolor=CARD2, tcolor=MUTED).pack(side="left")
        self.csv_status = ctk.CTkLabel(csv_btn_row, text="",
                                        font=ctk.CTkFont(family="Georgia", size=15), text_color=GREEN)
        self.csv_status.pack(side="left", padx=10)

        # ── OPTION B: Live sync via service account (advanced) ───────────
        opt_b = ctk.CTkFrame(gs_f, fg_color=CARD2, corner_radius=8)
        opt_b.pack(fill="x", padx=16, pady=(6,12))
        ctk.CTkLabel(opt_b, text="⚙️  Option B — Live Sync to Google Sheet  (one-time setup)",
                     font=ctk.CTkFont(family="Georgia", size=16, weight="bold"),
                     text_color=GOLD).pack(anchor="w", padx=12, pady=(8,2))

        status_txt = "✅ gspread installed" if GSPREAD_OK else "⚠️  First run:  pip install gspread google-auth"
        ctk.CTkLabel(opt_b, text=status_txt,
                     font=ctk.CTkFont(family="Georgia", size=15, slant="italic"),
                     text_color=GREEN if GSPREAD_OK else ORANGE
                     ).pack(anchor="w", padx=12, pady=(0,4))

        guide_steps = (
            "Step 1 → console.cloud.google.com → New Project → Enable 'Sheets API' + 'Drive API'\n"
            "Step 2 → IAM & Admin → Service Accounts → Create → Download JSON key\n"
            "Step 3 → Open your Google Sheet → Share with the service account email from the JSON\n"
            "Step 4 → Copy Sheet ID from URL: ...spreadsheets/d/[COPY THIS]/edit\n"
            "Step 5 → Fill in the fields below and click Sync"
        )
        ctk.CTkLabel(opt_b, text=guide_steps,
                     font=ctk.CTkFont(family="Georgia", size=14), text_color=MUTED,
                     justify="left", wraplength=560).pack(anchor="w", padx=12, pady=(0,8))

        gs_rows = [("Sheet ID:", "gsheet_id", 280),
                   ("JSON key path:", "gsheet_key_path", 280)]
        self.gs_entries = {}
        for lbl_txt, key, w_ in gs_rows:
            r = ctk.CTkFrame(opt_b, fg_color="transparent")
            r.pack(fill="x", padx=12, pady=3)
            ctk.CTkLabel(r, text=lbl_txt, width=130,
                         font=ctk.CTkFont(family="Georgia", size=16), text_color=MUTED, anchor="w").pack(side="left")
            e = entry(r, "", w_)
            e.insert(0, self.cfg.get(key))
            e.pack(side="left", padx=(0,6))
            if key == "gsheet_key_path":
                btn(r, "Browse", lambda _e=e: self._browse_json(_e), w=70, h=32, size=15,
                    color=CARD2, hcolor=CARD, tcolor=WHITE).pack(side="left")
            self.gs_entries[key] = e

        gs_btn_row = ctk.CTkFrame(opt_b, fg_color="transparent")
        gs_btn_row.pack(fill="x", padx=12, pady=(4,10))
        btn(gs_btn_row, "🔄  Sync to Google Sheet", self._sync_gsheet,
            w=200, h=36, size=16).pack(side="left", padx=(0,10))
        self.gs_status = ctk.CTkLabel(gs_btn_row, text="",
                                       font=ctk.CTkFont(family="Georgia", size=15), text_color=GREEN, wraplength=300)
        self.gs_status.pack(side="left")

                                                                       
        btn(scroll, "✅  Save All Settings", self._save,
            w=200, h=44, size=19).pack(anchor="w", padx=24, pady=16)
        self.save_st = ctk.CTkLabel(scroll, text="",
                                     font=ctk.CTkFont(family="Georgia", size=18, weight="bold"),
                                     text_color=GREEN)
        self.save_st.pack(anchor="w", padx=24)

    def _toggle_dark(self):
        """Live-switch appearance mode when the toggle is flipped, and persist immediately."""
        mode = self._dm_var.get()
        ctk.set_appearance_mode(mode)
        # Persist immediately so restart remembers the choice
        self.cfg.set("dark_mode", "1" if mode == "dark" else "0")

    # ── CSV export (Option A — instant, no setup) ────────────────────────
    def _export_csv(self):
        """Export all bookings to CSV. User can drag it into Google Sheets."""
        import csv, tempfile
        EXPORTS_DIR = "exports"
        os.makedirs(EXPORTS_DIR, exist_ok=True)
        ts   = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(EXPORTS_DIR, f"dhanak_bookings_{ts}.csv")
        rows = self.db.recent(9999)            # all bookings
        header = ["ID","Name","CNIC","Phone","Booking Time","Event Date","Shift",
                  "Persons","Menu","Event Type","Rate","Total","Advance",
                  "Filer","PRA Tax","FBR Tax","Cleared","Notes"]
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(header)
            for b in rows:
                total = (b.get("persons",0) or 0) * (b.get("rate",0) or 0)
                w.writerow([
                    b["id"], b["customer_name"], b.get("cnic",""), b.get("phone",""),
                    b.get("booking_time",""), b.get("event_date",""), b.get("shift",""),
                    b.get("persons",0), b.get("menu_type",""), b.get("event_type",""),
                    b.get("rate",0), total, b.get("advance",0),
                    b.get("filer_status",""), b.get("pra_tax",0), b.get("fbr_tax",0),
                    "YES" if b.get("tax_paid") else "NO",
                    b.get("notes","")
                ])
        self.csv_status.configure(
            text=f"✅ Exported {len(rows)} rows → {path}", text_color=GREEN)
        self.after(200, lambda: self._open_exports_folder())

    def _open_exports_folder(self):
        EXPORTS_DIR = "exports"
        os.makedirs(EXPORTS_DIR, exist_ok=True)
        if sys.platform == "win32":   os.startfile(EXPORTS_DIR)
        elif sys.platform == "darwin": subprocess.Popen(["open",    EXPORTS_DIR])
        else:                           subprocess.Popen(["xdg-open", EXPORTS_DIR])

    def _save(self):
        self.cfg.set("api_key", self.api_e.get().strip())
        for k, e in self.info_e.items():
            self.cfg.set(k, e.get().strip())
        for k, e in getattr(self, "gs_entries", {}).items():
            self.cfg.set(k, e.get().strip())
        # Save dark mode preference
        self.cfg.set("dark_mode", "1" if self._dm_var.get() == "dark" else "0")
        self.save_st.configure(text="✅ Settings saved successfully!")
        self.after(3000, lambda: self.save_st.configure(text=""))

    def _browse_json(self, entry_widget):
        path = filedialog.askopenfilename(
            title="Select Service Account JSON",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")])
        if path:
            entry_widget.delete(0, "end")
            entry_widget.insert(0, path)

    def _sync_gsheet(self):
        if not GSPREAD_OK:
            self.gs_status.configure(text="Install gspread: pip install gspread google-auth", text_color=ORANGE)
            return
        sheet_id  = self.gs_entries["gsheet_id"].get().strip()
        key_path  = self.gs_entries["gsheet_key_path"].get().strip()
        if not sheet_id or not key_path:
            self.gs_status.configure(text="Please fill in Sheet ID and JSON key path.", text_color=ORANGE)
            return
        self.gs_status.configure(text="⏳ Syncing…", text_color=MUTED)
        self.update()
        def _do_sync():
            try:
                scope  = ["https://spreadsheets.google.com/feeds",
                          "https://www.googleapis.com/auth/drive"]
                creds  = Credentials.from_service_account_file(key_path, scopes=scope)
                gc     = gspread.authorize(creds)
                sh     = gc.open_by_key(sheet_id)
                try:    ws = sh.worksheet("Dhanak Bookings")
                except: ws = sh.add_worksheet("Dhanak Bookings", rows=2000, cols=20)
                rows   = self.db.recent(500)
                header = ["ID","Name","CNIC","Phone","Booking Time","Event Date","Shift",
                          "Persons","Menu","Event Type","Rate","Advance","Filer","PRA","FBR","Cleared","Notes"]
                data   = [header]
                for b in rows:
                    total = (b.get("persons",0) or 0) * (b.get("rate",0) or 0)
                    data.append([
                        b["id"], b["customer_name"], b.get("cnic",""), b.get("phone",""),
                        b.get("booking_time",""), b.get("event_date",""), b.get("shift",""),
                        b.get("persons",0), b.get("menu_type",""), b.get("event_type",""),
                        b.get("rate",0), b.get("advance",0), b.get("filer_status",""),
                        b.get("pra_tax",0), b.get("fbr_tax",0),
                        "YES" if b.get("tax_paid") else "NO",
                        b.get("notes","")
                    ])
                ws.clear()
                ws.update("A1", data)
                self.after(0, lambda: self.gs_status.configure(
                    text=f"✅ Synced {len(rows)} rows to Google Sheet.", text_color=GREEN))
            except Exception as ex:
                self.after(0, lambda e=str(ex): self.gs_status.configure(
                    text=f"❌ {e[:100]}", text_color=RED))
        threading.Thread(target=_do_sync, daemon=True).start()

    def _backup(self):
        try:
            p = self.db.backup()
            self.bk_st.configure(text=f"✅ {os.path.basename(p)}", text_color=GREEN)
        except Exception as e:
            self.bk_st.configure(text=f"❌ {e}", text_color=RED)

    def _open_folder(self):
        os.makedirs(BACKUP_DIR, exist_ok=True)
        if sys.platform == "win32":   os.startfile(BACKUP_DIR)
        elif sys.platform == "darwin": subprocess.Popen(["open", BACKUP_DIR])
        else:                          subprocess.Popen(["xdg-open", BACKUP_DIR])

                                                                      
                         
                                                                      

class UpcomingTab(ctk.CTkFrame):
    def __init__(self, parent, db: DB, gen: ReceiptGen):
        super().__init__(parent, fg_color="transparent")
        self.db  = db
        self.gen = gen
        self._build()
        self.refresh()

    def _build(self):
        top = ctk.CTkFrame(self, bg_color=BG, fg_color=CARD, corner_radius=12,
                           border_width=2, border_color=BORDER)
        top.pack(fill="x", pady=(0,10))
        ctk.CTkLabel(top, text="🗓️  Upcoming Bookings",
                     font=ctk.CTkFont(family="Georgia", size=16, weight="bold"),
                     text_color=GOLD).pack(side="left", padx=16, pady=12)
        btn(top, "🔄 Refresh", self.refresh, w=100, h=36, size=17,
            color=CARD, hcolor=CARD2, tcolor=MUTED).pack(side="right", padx=12, pady=10)
        self.count_lbl = ctk.CTkLabel(top, text="",
                                       font=ctk.CTkFont(family="Georgia", size=18), text_color=MUTED)
        self.count_lbl.pack(side="right", padx=6)

        cols = ("Date","Shift","Customer","Phone","Event","Persons","Total","Advance","Balance","Status")
        wids = (90, 55, 140, 110, 90, 65, 85, 80, 80, 75)
        frame = ctk.CTkFrame(self, bg_color=BG, fg_color=CARD, corner_radius=12,
                             border_width=2, border_color=BORDER)
        frame.pack(fill="both", expand=True)
        self.tv = tree_setup(frame, cols, wids)
        self.tv.bind("<Double-1>", lambda e: self._open_receipt())

    def refresh(self):
        rows = self.db.upcoming()
        self.count_lbl.configure(text=f"{len(rows)} upcoming")
        for i in self.tv.get_children(): self.tv.delete(i)
        for b in rows:
            total  = (b.get("persons",0) or 0) * (b.get("rate",0) or 0)
            rem    = max(0, total - (b.get("advance",0) or 0) - (b.get("final_payment",0) or 0))
            status = "✅ CLEARED" if b.get("tax_paid") else ("⚠️ Balance" if rem > 0 else "—")
            self.tv.insert("", "end", iid=str(b["id"]), values=(
                b["event_date"], b["shift"], b["customer_name"],
                b.get("phone",""), b.get("event_type",""),
                b.get("persons",""),
                f"Rs.{int(total):,}", f"Rs.{int(b.get('advance',0) or 0):,}",
                f"Rs.{int(rem):,}", status
            ))

    def _open_receipt(self):
        sel = self.tv.selection()
        if not sel: return
        b = self.db.get(int(sel[0]))
        if b: ReceiptDialog(self, b, self.gen, self.db, start_tab="booking")

                                                                      
                        
                                                                      

class CustomerTab(ctk.CTkFrame):
    def __init__(self, parent, db: DB, gen: ReceiptGen):
        super().__init__(parent, fg_color="transparent")
        self.db  = db
        self.gen = gen
        self._build()
        self.refresh_customers()

    def _build(self):
        pane = ctk.CTkFrame(self, bg_color=BG, fg_color="transparent")
        pane.pack(fill="both", expand=True)

                             
        left = ctk.CTkFrame(pane, bg_color=BG, fg_color=PANEL, corner_radius=12, width=340,
                            border_width=2, border_color=BORDER)
        left.pack(side="left", fill="y", padx=(0,10))
        left.pack_propagate(False)

        ctk.CTkLabel(left, text="👥  Customers",
                     font=ctk.CTkFont(family="Georgia", size=16, weight="bold"),
                     text_color=GOLD).pack(anchor="w", padx=16, pady=(16,8))

        search_row = ctk.CTkFrame(left, fg_color="transparent")
        search_row.pack(fill="x", padx=12, pady=(0,8))
        self.cq = entry(search_row, "Search customers…", 220)
        self.cq.pack(side="left", fill="x", expand=True, padx=(0,6))
        self.cq.bind("<KeyRelease>", lambda e: self._search_customers())

        cols = ("Name","Phone","Bookings","Spent")
        wids = (120, 100, 65, 85)
        cframe = ctk.CTkFrame(left, bg_color=PANEL, fg_color=CARD2, corner_radius=8,
                              border_width=2, border_color=BORDER)
        cframe.pack(fill="both", expand=True, padx=8, pady=(0,8))
        self.ctv = tree_setup(cframe, cols, wids)
        self.ctv.bind("<<TreeviewSelect>>", lambda e: self._on_select())

                                
        self.right = ctk.CTkFrame(pane, bg_color=BG, fg_color=CARD, corner_radius=12,
                                  border_width=2, border_color=BORDER)
        self.right.pack(side="right", fill="both", expand=True)

        self.detail_lbl = ctk.CTkLabel(
            self.right, text="← Select a customer to view history",
            font=ctk.CTkFont(family="Georgia", size=19), text_color=MUTED)
        self.detail_lbl.pack(expand=True)

    def refresh_customers(self):
        rows = self.db.all_customers()
        self._load_customers(rows)

    def _load_customers(self, rows):
        for i in self.ctv.get_children(): self.ctv.delete(i)
        for c in rows:
            self.ctv.insert("", "end", iid=str(c["id"]), values=(
                c["name"], c["phone"],
                c["total_bookings"],
                f"Rs.{int(c.get('total_spent',0) or 0):,}"
            ))

    def _search_customers(self):
        q = self.cq.get().strip()
        if q: self._load_customers(self.db.search_customers(q))
        else: self.refresh_customers()

    def _on_select(self):
        sel = self.ctv.selection()
        if not sel: return
        item = self.ctv.item(sel[0], "values")
        phone = item[1] if item else ""
        self._show_history(phone)

    def _show_history(self, phone):
        for w in self.right.winfo_children(): w.destroy()

        bookings = self.db.customer_history(phone)
        if not bookings:
            ctk.CTkLabel(self.right, text="No bookings found.",
                         text_color=MUTED).pack(expand=True)
            return

        b0 = bookings[0]
        total_spent = sum((b.get("persons",0) or 0)*(b.get("rate",0) or 0) for b in bookings)

        info_frame = ctk.CTkFrame(self.right, bg_color=CARD, fg_color=CARD2, corner_radius=12,
                                  border_width=2, border_color=BORDER)
        info_frame.pack(fill="x", padx=16, pady=16)

        ctk.CTkLabel(info_frame,
                     text=f"  {b0.get('customer_name','')}",
                     font=ctk.CTkFont(family="Georgia", size=22, weight="bold"),
                     text_color=GOLD).pack(anchor="w", padx=12, pady=(10,2))
        ctk.CTkLabel(info_frame,
                     text=f"  📞 {b0.get('phone','')}   🪪 {b0.get('cnic','')}",
                     font=ctk.CTkFont(family="Georgia", size=17), text_color=MUTED).pack(anchor="w", padx=12, pady=(0,2))
        addr_text = b0.get("home_address","") or "—"
        ctk.CTkLabel(info_frame,
                     text=f"  🏠 {addr_text}",
                     font=ctk.CTkFont(family="Georgia", size=16), text_color=MUTED).pack(anchor="w", padx=12, pady=(0,4))

        cards = ctk.CTkFrame(info_frame, fg_color="transparent")
        cards.pack(fill="x", padx=8, pady=(4,12))
        for lbl, val, col in [
            ("Total Bookings", str(len(bookings)), GOLD),
            ("Total Spent",    f"Rs.{int(total_spent):,}", GREEN),
            ("First Event",    (bookings[-1].get("event_date","") if bookings else ""), BLUE),
            ("Last Event",     (bookings[0].get("event_date","") if bookings else ""), ORANGE),
        ]:
            cf = ctk.CTkFrame(cards, fg_color=CARD2, corner_radius=10, width=130, height=58,
                              border_width=2, border_color=BORDER)
            cf.pack(side="left", padx=6)
            cf.pack_propagate(False)
            ctk.CTkLabel(cf, text=val, font=ctk.CTkFont(family="Georgia", size=18, weight="bold"),
                         text_color=col).pack(pady=(8,0))
            ctk.CTkLabel(cf, text=lbl, font=ctk.CTkFont(family="Georgia", size=15),
                         text_color=MUTED).pack()

        ctk.CTkLabel(self.right, text="Booking History",
                     font=ctk.CTkFont(family="Georgia", size=18, weight="bold"),
                     text_color=GOLD).pack(anchor="w", padx=16, pady=(0,6))

        hist_frame = ctk.CTkFrame(self.right, bg_color=CARD, fg_color=CARD, corner_radius=12,
                                  border_width=2, border_color=BORDER)
        hist_frame.pack(fill="both", expand=True, padx=16, pady=(0,16))

        cols = ("Date","Shift","Event","Persons","Total","Advance","Status")
        wids = (90, 55, 90, 65, 90, 85, 80)
        htv = tree_setup(hist_frame, cols, wids)
        for b in bookings:
            total = (b.get("persons",0) or 0) * (b.get("rate",0) or 0)
            rem   = max(0, total - (b.get("advance",0) or 0) - (b.get("final_payment",0) or 0))
            status = "CANCELLED" if b.get("is_cancelled") else (
                "✅ CLEARED" if b.get("tax_paid") else ("⚠️ Balance" if rem > 0 else "—"))
            htv.insert("", "end", values=(
                b["event_date"], b["shift"], b.get("event_type",""),
                b.get("persons",""),
                f"Rs.{int(total):,}", f"Rs.{int(b.get('advance',0) or 0):,}",
                status
            ))

                                                                      
                  
                                                                      

                                                                      
                                                               
                                                                      

class DhanakApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        _dm = Config().get("dark_mode","0")
        # Force a moody, Old Money dark base; light mode just slightly brightens CTk widgets.
        ctk.set_appearance_mode("dark" if _dm == "1" else "dark")
        ctk.set_default_color_theme("dark-blue")
        self.title(f"{APP_NAME}  {APP_VER}")
        self.geometry("1440x860")
        self.minsize(1100, 700)
        self.configure(fg_color=BG)
        self.cfg   = Config()
        self.db    = DB()
        self.gen   = ReceiptGen(self.cfg)
        self.voice = Voice(self.db, self.cfg)
        self._topbar()
        self._main()
        self._show("bookings")
        self.protocol("WM_DELETE_WINDOW", self._quit)

    def _topbar(self):
        tb = ctk.CTkFrame(self, bg_color=BG, fg_color=PANEL, corner_radius=0, height=64,
                          border_width=0)
        tb.pack(side="top", fill="x")
        tb.pack_propagate(False)

        logo_frame = ctk.CTkFrame(tb, fg_color="transparent")
        logo_frame.pack(side="left", padx=(20, 0))

        _logo_loaded = False
        if PIL_OK:
            for _lp in ["dhanak_logo.png",
                        os.path.join(os.path.dirname(os.path.abspath(__file__)), "dhanak_logo.png")]:
                if os.path.exists(_lp):
                    try:
                        pil_img = PILImage.open(_lp).convert("RGBA")
                        pil_img.thumbnail((42, 42), PILImage.LANCZOS)
                        ctk_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img,
                                               size=(42, 42))
                        ctk.CTkLabel(logo_frame, image=ctk_img, text="",
                                     fg_color="transparent").pack(side="left", pady=11)
                        _logo_loaded = True
                        break
                    except Exception:
                        pass

        ctk.CTkLabel(logo_frame,
                     text="  DHANAK" if _logo_loaded else "DHANAK",
                     font=ctk.CTkFont(family="Georgia", size=22, weight="bold"),
                     text_color=GOLD, fg_color="transparent").pack(side="left", pady=11)

        sep = ctk.CTkFrame(tb, width=1, fg_color=BORDER)
        sep.pack(side="left", fill="y", padx=24, pady=16)

        nav_items = [
            ("Bookings",    "bookings"),
            ("AI Assistant","voice"),
            ("Calendar",    "calendar"),
            ("Upcoming",    "upcoming"),
            ("Customers",   "customers"),
            ("Reports",     "reports"),
            ("Settings",    "settings"),
        ]
        nav_row = ctk.CTkFrame(tb, fg_color="transparent")
        nav_row.pack(side="left", fill="x", expand=True)

        self.nav_btns = {}
        for lbl, tid in nav_items:
            b = ctk.CTkButton(nav_row, text=lbl,
                              command=lambda t=tid: self._show(t),
                              height=40, anchor="center",
                              fg_color="transparent",
                              hover_color=CARD2,
                              text_color=MUTED,
                              font=ctk.CTkFont(family="Georgia", size=17, weight="bold"),
                              corner_radius=12,
                              border_width=0)
            b.pack(side="left", padx=4, pady=12, expand=True, fill="x")
            self.nav_btns[tid] = b

        ctk.CTkLabel(tb, text=APP_VER,
                     font=ctk.CTkFont(family="Georgia", size=14), text_color=MUTED,
                     fg_color="transparent").pack(side="right", padx=20)

        glow = ctk.CTkFrame(self, fg_color=PURPLE_GLOW, corner_radius=0, height=2)
        glow.pack(side="top", fill="x")

    def _main(self):
        self.main = ctk.CTkFrame(self, bg_color=BG, fg_color=BG, corner_radius=0)
        self.main.pack(side="top", fill="both", expand=True, padx=20, pady=16)

        def on_change():
            if hasattr(self, "tabs"):
                self.tabs["calendar"].draw()
                if "upcoming" in self.tabs:
                    self.tabs["upcoming"].refresh()
                if "customers" in self.tabs:
                    self.tabs["customers"].refresh_customers()

        self.tabs = {
            "bookings":  BookingsTab(self.main, self.db, self.gen, on_change=on_change),
            "voice":     VoiceTab(self.main, self.voice),
            "calendar":  CalendarTab(self.main, self.db),
            "upcoming":  UpcomingTab(self.main, self.db, self.gen),
            "customers": CustomerTab(self.main, self.db, self.gen),
            "reports":   ReportsTab(self.main, self.db, self.gen, self.cfg),
            "settings":  SettingsTab(self.main, self.cfg, self.db),
        }

    def _show(self, tid):
        for t in self.tabs.values(): t.pack_forget()
        self.tabs[tid].pack(fill="both", expand=True)
        for k, b in self.nav_btns.items():
            if k == tid:
                b.configure(fg_color=GOLD, text_color="#1E1B10",
                            border_width=2, border_color=GOLD_DK)
            else:
                b.configure(fg_color="transparent", text_color=MUTED,
                            border_width=0)

    def _quit(self):
        try: self.db.backup()
        except: pass
        self.destroy()

                                                                      
              
                                                                      

if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(sys.argv[0])))
    app = DhanakApp()
    app.mainloop()
