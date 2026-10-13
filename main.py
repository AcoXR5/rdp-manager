#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RDP Manager - Mobile (KivyMD) - Android build
"""

import json, os, socket, time, uuid, webbrowser
from datetime import datetime
from threading import Thread
from concurrent.futures import ThreadPoolExecutor

from kivy.clock import Clock, mainthread
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView

from kivymd.app import MDApp
from kivymd.uix.screen import MDScreen
from kivymd.uix.card import MDCard
from kivymd.uix.label import MDLabel
from kivymd.uix.button import (MDRaisedButton, MDFlatButton,
                                MDFloatingActionButton)
from kivymd.uix.textfield import MDTextField
from kivymd.uix.dialog import MDDialog
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.toolbar import MDTopAppBar
from kivymd.uix.scrollview import MDScrollView
from kivymd.uix.list import OneLineListItem

BG         = (0.05, 0.05, 0.08, 1)
SURFACE    = (0.086, 0.086, 0.12, 1)
SURFACE_HI = (0.118, 0.118, 0.16, 1)
TEXT       = (0.91, 0.91, 0.94, 1)
TEXT_DIM   = (0.54, 0.54, 0.63, 1)
TEXT_MUTE  = (0.34, 0.34, 0.45, 1)
ACCENT     = (0.55, 0.50, 1.0, 1)
GREEN      = (0.29, 0.87, 0.50, 1)
RED        = (0.97, 0.44, 0.44, 1)
YELLOW     = (0.98, 0.75, 0.14, 1)

APP_DIR = os.path.join(os.path.expanduser("~"), ".rdp_manager_mobile")
os.makedirs(APP_DIR, exist_ok=True)
CONFIG_FILE = os.path.join(APP_DIR, "connections.json")


def tcp_check_detailed(host, port=3389, timeout=2.5):
    if not host:
        return False, None, "No host specified"
    t0 = time.perf_counter()
    try:
        with socket.create_connection((host, int(port)), timeout=timeout):
            return True, round((time.perf_counter()-t0)*1000, 1), None
    except socket.timeout:
        return False, None, f"Timeout ({timeout}s) — host unreachable or firewall blocks port {port}"
    except socket.gaierror as e:
        return False, None, f"DNS error — cannot resolve hostname ({e})"
    except ConnectionRefusedError:
        return False, None, f"Connection refused on port {port} — RDP service not running?"
    except ConnectionResetError:
        return False, None, "Connection reset by peer"
    except OSError as e:
        return False, None, f"Network error: {e}"
    except Exception as e:
        return False, None, f"Error: {e}"


def tcp_ping_detailed(host, port=3389, count=3, timeout=2.0):
    res = []
    last_err = None
    for _ in range(count):
        ok, lat, err = tcp_check_detailed(host, port, timeout)
        if ok: res.append(lat)
        else: last_err = err
        time.sleep(0.1)
    if not res:
        return False, None, None, None, None, last_err or "Unknown error"
    avg = sum(res)/len(res)
    jit = sum(abs(res[i]-res[i-1]) for i in range(1, len(res)))/(len(res)-1) if len(res) > 1 else 0
    return True, round(avg,1), round(min(res),1), round(max(res),1), round(jit,1), None


def launch_rdp_mobile(conn):
    host = conn.get("host", "")
    port = conn.get("port", 3389)
    if not host:
        return False
    url = f"rdp://full%20address=s:{host}:{port}"
    if conn.get("username"):
        url += f"&username=s:{conn['username']}"
    try:
        webbrowser.open(url)
        return True
    except Exception:
        return False


class LongPressCard(MDCard):
    def __init__(self, conn, on_tap, on_long_press, **kwargs):
        super().__init__(**kwargs)
        self.conn = conn
        self._on_tap_cb = on_tap
        self._on_long_press_cb = on_long_press
        self._press_clock = None
        self._press_start = (0, 0)
        self._long_pressed = False

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            self._long_pressed = False
            self._press_start = touch.pos
            if self._press_clock:
                self._press_clock.cancel()
            self._press_clock = Clock.schedule_once(self._trigger_long_press, 0.55)
        return super().on_touch_down(touch)

    def on_touch_move(self, touch):
        if self._press_clock:
            dx = abs(touch.pos[0] - self._press_start[0])
            dy = abs(touch.pos[1] - self._press_start[1])
            if dx > dp(18) or dy > dp(18):
                self._press_clock.cancel()
                self._press_clock = None
        return super().on_touch_move(touch)

    def on_touch_up(self, touch):
        if self._press_clock:
            self._press_clock.cancel()
            self._press_clock = None
            if self.collide_point(*touch.pos) and not self._long_pressed:
                if self._on_tap_cb:
                    self._on_tap_cb(self.conn)
                return True
        return super().on_touch_up(touch)

    def _trigger_long_press(self, dt):
        self._press_clock = None
        self._long_pressed = True
        if self._on_long_press_cb:
            self._on_long_press_cb(self.conn)


class ConnCard(LongPressCard):
    def __init__(self, conn, on_tap, on_long_press, **kwargs):
        super().__init__(
            conn=conn, on_tap=on_tap, on_long_press=on_long_press,
            orientation="vertical",
            size_hint_y=None, height=dp(126),
            radius=[dp(14)], md_bg_color=SURFACE, elevation=0,
            padding=[dp(14), dp(12), dp(14), dp(12)],
            spacing=dp(2), **kwargs)
        self._build()

    def _build(self):
        header = MDBoxLayout(orientation="horizontal",
                              size_hint_y=None, height=dp(26))
        self.dot = MDLabel(text="●", theme_text_color="Custom",
                            text_color=TEXT_MUTE, size_hint_x=None,
                            width=dp(22), font_style="H6")
        header.add_widget(self.dot)
        self.name_lbl = MDLabel(text=self.conn.get("name", ""),
                                 theme_text_color="Custom", text_color=TEXT,
                                 font_style="H6", bold=True)
        header.add_widget(self.name_lbl)
        self.ping_lbl = MDLabel(text="—", theme_text_color="Custom",
                                 text_color=TEXT_MUTE, font_style="H6",
                                 halign="right", size_hint_x=None, width=dp(80))
        header.add_widget(self.ping_lbl)
        self.add_widget(header)

        line = f"{self.conn.get('host','')}:{self.conn.get('port',3389)}"
        if self.conn.get("username"):
            line += f"  ·  {self.conn['username']}"
        self.host_lbl = MDLabel(text=line, theme_text_color="Custom",
                                 text_color=TEXT_DIM, font_style="Caption",
                                 size_hint_y=None, height=dp(18))
        self.add_widget(self.host_lbl)

        info = self.conn.get("sysinfo")
        if info:
            cpu_short = " ".join((info.get("cpu_name") or "CPU").split()[:3])
            specs = (f"⚙  {cpu_short}  ·  {info.get('cores','?')}C/"
                     f"{info.get('threads','?')}T  ·  {info.get('ram_gb','?')} GB")
            specs_color = TEXT_DIM
        else:
            specs = "◌  No sysinfo — long-press → Sysinfo"
            specs_color = TEXT_MUTE
        self.specs_lbl = MDLabel(text=specs, theme_text_color="Custom",
                                  text_color=specs_color, font_style="Caption",
                                  size_hint_y=None, height=dp(18))
        self.add_widget(self.specs_lbl)

        self.reason_lbl = MDLabel(text="", theme_text_color="Custom",
                                   text_color=RED, font_style="Caption",
                                   size_hint_y=None, height=dp(16), shorten=True)
        self.add_widget(self.reason_lbl)

        self.status_lbl = MDLabel(text="CHECKING", theme_text_color="Custom",
                                   text_color=TEXT_MUTE, font_style="Caption",
                                   size_hint_y=None, height=dp(18))
        self.add_widget(self.status_lbl)

    def update_status(self, st):
        alive = st.get("alive")
        if alive is True:
            self.dot.text_color = GREEN
            self.status_lbl.text = "● ONLINE"
            self.status_lbl.text_color = GREEN
            self.reason_lbl.text = ""
        elif alive is False:
            self.dot.text_color = RED
            self.status_lbl.text = "● OFFLINE"
            self.status_lbl.text_color = RED
            err = st.get("error") or ""
            short = err[:60] + ("…" if len(err) > 60 else "")
            self.reason_lbl.text = f"⚠ {short}"
        else:
            self.dot.text_color = TEXT_MUTE
            self.status_lbl.text = "● CHECKING"
            self.status_lbl.text_color = TEXT_MUTE
            self.reason_lbl.text = ""

        lat = st.get("latency")
        if lat is not None:
            color = GREEN if lat < 60 else (YELLOW if lat < 150 else RED)
            self.ping_lbl.text = f"{lat:.0f} ms"
            self.ping_lbl.text_color = color
        else:
            self.ping_lbl.text = "—"
            self.ping_lbl.text_color = TEXT_MUTE


class HomeScreen(MDScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.name = "home"
        self._build()

    def _build(self):
        root = MDBoxLayout(orientation="vertical")

        self.toolbar = MDTopAppBar(
            title="RDP Manager", elevation=0, md_bg_color=BG,
            specific_text_color=TEXT, anchor_title="left")
        self.toolbar.left_action_items = [["refresh", lambda x: self.app.confirm_refresh_all()]]
        self.toolbar.right_action_items = [["magnify", lambda x: self.toggle_search()]]
        root.add_widget(self.toolbar)

        self.search = MDTextField(hint_text="Search...", mode="rectangle",
                                   size_hint_x=1, size_hint_y=None, height=dp(50))
        self.search.opacity = 0
        self.search.disabled = True
        self.search.bind(text=lambda *_: self.refresh_cards())
        root.add_widget(self.search)

        self.status_lbl = MDLabel(text="Ready.", theme_text_color="Custom",
                                   text_color=TEXT_DIM, font_style="Caption",
                                   size_hint_y=None, height=dp(22),
                                   padding=[dp(14), 0])
        root.add_widget(self.status_lbl)

        self.scroll = MDScrollView()
        self.list_box = MDBoxLayout(orientation="vertical", spacing=dp(10),
                                     padding=[dp(12), dp(6), dp(12), dp(90)],
                                     size_hint_y=None)
        self.list_box.bind(minimum_height=self.list_box.setter("height"))
        self.scroll.add_widget(self.list_box)
        root.add_widget(self.scroll)

        self.fab = MDFloatingActionButton(
            icon="plus", md_bg_color=ACCENT,
            pos_hint={"right": 0.95, "y": 0.03},
            on_release=lambda x: self.app.open_add_dialog())
        self.add_widget(self.fab)

        self.add_widget(root)

    @property
    def app(self):
        return MDApp.get_running_app()

    def toggle_search(self):
        if self.search.opacity == 0:
            self.search.opacity = 1
            self.search.disabled = False
            self.search.focus = True
        else:
            self.search.opacity = 0
            self.search.disabled = True
            self.search.text = ""

    def refresh_cards(self):
        self.list_box.clear_widgets()
        q = (self.search.text or "").lower().strip()
        items = self.app.connections
        if q:
            items = [c for c in items if q in (
                c.get("name","") + " " + c.get("host","") + " " +
                c.get("username","") + " " + c.get("group","")).lower()]

        if not items:
            self.list_box.add_widget(MDLabel(
                text=("No connections — tap ＋ to add" if not self.app.connections
                      else "No results"),
                halign="center", theme_text_color="Custom",
                text_color=TEXT_MUTE, size_hint_y=None, height=dp(80)))
            self.update_status_bar()
            return

        for c in items:
            card = ConnCard(conn=c, on_tap=self.app.on_card_tap,
                             on_long_press=self.app.on_card_long_press)
            self.list_box.add_widget(card)
            card.update_status(self.app.status_by_id.get(c["id"], {}))

        self.update_status_bar()

    def update_status_bar(self):
        total = len(self.app.connections)
        on = sum(1 for c in self.app.connections
                 if self.app.status_by_id.get(c["id"], {}).get("alive") is True)
        off = sum(1 for c in self.app.connections
                  if self.app.status_by_id.get(c["id"], {}).get("alive") is False)
        unk = total - on - off
        self.status_lbl.text = (f"{total} servers   ·   ● {on} online   ·   "
                                 f"● {off} offline   ·   ● {unk} unknown")


class RDPManagerMobile(MDApp):
    def build(self):
        self.theme_cls.theme_style = "Dark"
        self.theme_cls.primary_palette = "DeepPurple"
        Window.clearcolor = BG

        self.connections = []
        self.status_by_id = {}
        self.selected_id = None
        self._executor = ThreadPoolExecutor(max_workers=4)
        self._load()

        self.home = HomeScreen()

        Clock.schedule_once(lambda dt: self.run_probes(), 0.4)
        Clock.schedule_interval(lambda dt: self.run_probes(), 30)
        return self.home

    def _load(self):
        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    self.connections = json.load(f)
        except Exception:
            self.connections = []
        for c in self.connections:
            self.status_by_id[c["id"]] = {
                "alive": None, "latency": None, "jitter": None,
                "min": None, "max": None, "last": None, "error": None,
            }

    def _save(self):
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.connections, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print("Save error:", e)

    def snack(self, text, duration=2.0):
        try:
            from kivymd.uix.snackbar import Snackbar
            Snackbar(text=text, duration=duration).open()
        except Exception:
            print(text)

    def run_probes(self):
        for c in list(self.connections):
            self._executor.submit(self._probe, c["id"])

    def _probe(self, cid):
        conn = next((c for c in self.connections if c["id"] == cid), None)
        if not conn: return
        st = self.status_by_id.setdefault(cid, {})
        alive, avg, mn, mx, jit, err = tcp_ping_detailed(
            conn.get("host",""), conn.get("port",3389), count=3, timeout=2.0)
        st["alive"] = alive
        st["latency"] = avg
        st["min"] = mn; st["max"] = mx; st["jitter"] = jit
        st["error"] = err if not alive else None
        st["last"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        Clock.schedule_once(lambda dt: self._refresh_home(), 0)

    @mainthread
    def _refresh_home(self):
        self.home.refresh_cards()

    def _confirm(self, title, text, on_yes, confirm_text="CONFIRM"):
        def yes(*a):
            dlg.dismiss()
            Clock.schedule_once(lambda dt: on_yes(), 0.05)
        dlg = MDDialog(
            title=title, text=text,
            buttons=[
                MDFlatButton(text="CANCEL", on_release=lambda x: dlg.dismiss()),
                MDRaisedButton(text=confirm_text, on_release=yes),
            ])
        dlg.open()

    def on_card_tap(self, conn):
        self.selected_id = conn["id"]
        self.open_detail_dialog(conn)

    def on_card_long_press(self, conn):
        self.selected_id = conn["id"]
        self.open_context_menu(conn)

    def open_context_menu(self, conn):
        content = MDBoxLayout(orientation="vertical", size_hint_y=None,
                               height=dp(6 * 50 + 8), spacing=0,
                               padding=[0, dp(4)])
        content.bind(minimum_height=content.setter("height"))
        dlg_ref = {"dlg": None}

        def close_and(cb):
            def inner(*a):
                if dlg_ref["dlg"]: dlg_ref["dlg"].dismiss()
                Clock.schedule_once(lambda dt: cb(), 0.05)
            return inner

        actions = [
            ("▶", "Connect",      lambda: self._connect(conn)),
            ("⟳", "Refresh",      lambda: self.confirm_refresh(conn)),
            ("ℹ", "Info",         lambda: self.open_info_dialog(conn)),
            ("⚠", "Show Reason",  lambda: self.open_reason_dialog(conn)),
            ("✎", "Edit",         lambda: self.open_edit_dialog(conn)),
            ("🗑", "Delete",       lambda: self.confirm_delete(conn)),
        ]
        for icon, label, cb in actions:
            color = RED if label == "Delete" else TEXT
            content.add_widget(OneLineListItem(
                text=f"  {icon}   {label}",
                theme_text_color="Custom", text_color=color,
                on_release=close_and(cb)))

        dlg = MDDialog(title=conn.get("name",""), type="custom",
                       content_cls=content,
                       buttons=[MDFlatButton(text="CLOSE",
                                              on_release=lambda x: dlg.dismiss())])
        dlg.open()
        dlg_ref["dlg"] = dlg

    def _connect(self, conn):
        st = self.status_by_id.get(conn["id"], {})
        if st.get("alive") is False:
            err = st.get("error") or "Unknown error"
            self._confirm("Server unreachable",
                          f"{conn.get('name','')} appears offline.\n\n"
                          f"Reason: {err}\n\nTry to connect anyway?",
                          lambda: self._do_connect(conn),
                          confirm_text="CONNECT ANYWAY")
        else:
            self._do_connect(conn)

    def _do_connect(self, conn):
        ok = launch_rdp_mobile(conn)
        if ok:
            self.snack(f"Opening RD Client for {conn.get('host','')}...")
        else:
            self.snack("No RDP client available")

    def confirm_refresh(self, conn):
        self._confirm("Confirm refresh",
                      f"Refresh this connection?\n\n"
                      f"{conn.get('name','')}\n"
                      f"{conn.get('host','')}:{conn.get('port',3389)}",
                      lambda: self._do_refresh_one(conn),
                      confirm_text="REFRESH")

    def _do_refresh_one(self, conn):
        self.snack(f"Refreshing {conn.get('name','')}...")
        self._executor.submit(self._probe, conn["id"])

    def confirm_refresh_all(self):
        if not self.connections:
            self.snack("No connections to check")
            return
        total = len(self.connections)
        self._confirm("Confirm Refresh All",
                      f"Refresh all {total} connections?",
                      self.refresh_all_with_report,
                      confirm_text="REFRESH ALL")

    def confirm_delete(self, conn):
        self._confirm("Confirm delete",
                      f"Delete this connection?\n\n"
                      f"{conn.get('name','')}\n"
                      f"{conn.get('host','')}:{conn.get('port',3389)}\n\n"
                      f"Cannot be undone.",
                      lambda: self._do_delete(conn),
                      confirm_text="DELETE")

    def _do_delete(self, conn):
        if conn in self.connections:
            self.connections.remove(conn)
        self.status_by_id.pop(conn["id"], None)
        if self.selected_id == conn["id"]:
            self.selected_id = None
        self._save()
        self._refresh_home()
        self.snack("Connection deleted")

    def refresh_all_with_report(self):
        if not self.connections:
            self.snack("No connections to check")
            return
        self.snack("Refreshing...")

        def worker():
            results = []
            for c in list(self.connections):
                alive, avg, mn, mx, jit, err = tcp_ping_detailed(
                    c.get("host",""), c.get("port",3389), count=3, timeout=2.5)
                st = self.status_by_id.setdefault(c["id"], {})
                st["alive"] = alive; st["latency"] = avg
                st["min"] = mn; st["max"] = mx; st["jitter"] = jit
                st["error"] = err if not alive else None
                st["last"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                results.append({
                    "id": c["id"], "name": c.get("name",""),
                    "host": f"{c.get('host','')}:{c.get('port',3389)}",
                    "alive": alive, "latency": avg, "error": err,
                })
                Clock.schedule_once(lambda dt: self._refresh_home(), 0)
            Clock.schedule_once(lambda dt: self.open_report_dialog(results), 0)

        Thread(target=worker, daemon=True).start()

    def open_detail_dialog(self, conn):
        st = self.status_by_id.get(conn["id"], {})
        info = conn.get("sysinfo") or {}

        content = MDBoxLayout(orientation="vertical", spacing=dp(4),
                               size_hint_y=None, padding=[dp(4)]*4)
        content.bind(minimum_height=content.setter("height"))

        alive = st.get("alive")
        if alive is True:
            color, text = GREEN, "● ONLINE"
        elif alive is False:
            color, text = RED, "● OFFLINE"
        else:
            color, text = TEXT_MUTE, "● UNKNOWN"
        content.add_widget(MDLabel(text=text, theme_text_color="Custom",
                                    text_color=color, font_style="H6",
                                    size_hint_y=None, height=dp(28)))

        if alive is False and st.get("error"):
            content.add_widget(MDLabel(text=st["error"],
                                        theme_text_color="Custom",
                                        text_color=RED, font_style="Caption",
                                        size_hint_y=None, height=dp(48)))

        def row(label, value):
            r = MDBoxLayout(orientation="horizontal", size_hint_y=None,
                            height=dp(26))
            r.add_widget(MDLabel(text=label, theme_text_color="Custom",
                                  text_color=TEXT_DIM, font_style="Body2",
                                  size_hint_x=0.42))
            r.add_widget(MDLabel(text=str(value or "—"),
                                  theme_text_color="Custom", text_color=TEXT,
                                  font_style="Body2", bold=True, halign="right"))
            content.add_widget(r)

        row("Address", f"{conn.get('host','')}:{conn.get('port',3389)}")
        row("Ping", f"{st.get('latency')} ms" if st.get("latency") is not None else "—")
        row("Jitter", f"±{st.get('jitter')} ms" if st.get("jitter") is not None else "—")
        row("Processor", info.get("cpu_name","—"))
        row("Cores", f"{info.get('cores','—')}C / {info.get('threads','—')}T")
        row("RAM", f"{info.get('ram_gb','—')} GB")
        row("OS", info.get("os","—"))
        row("Hostname", info.get("hostname","—"))

        dlg_ref = {"dlg": None}
        def close_and(cb):
            def inner(*a):
                if dlg_ref["dlg"]: dlg_ref["dlg"].dismiss()
                Clock.schedule_once(lambda dt: cb(), 0.05)
            return inner

        dlg = MDDialog(title=conn.get("name",""), type="custom",
                       content_cls=content,
                       buttons=[
                           MDFlatButton(text="DELETE",
                                         theme_text_color="Custom",
                                         text_color=RED,
                                         on_release=close_and(
                                             lambda: self.confirm_delete(conn))),
                           MDFlatButton(text="EDIT",
                                         on_release=close_and(
                                             lambda: self.open_edit_dialog(conn))),
                           MDFlatButton(text="SYSINFO",
                                         on_release=close_and(
                                             lambda: self.open_sysinfo_dialog(conn))),
                           MDRaisedButton(text="CONNECT",
                                           on_release=close_and(
                                               lambda: self._connect(conn))),
                       ])
        dlg.open()
        dlg_ref["dlg"] = dlg

    def open_info_dialog(self, conn):
        st = self.status_by_id.get(conn["id"], {})
        info = conn.get("sysinfo") or {}
        alive = st.get("alive")

        content = MDBoxLayout(orientation="vertical", spacing=dp(4),
                               size_hint_y=None, padding=[dp(4)]*4)
        content.bind(minimum_height=content.setter("height"))

        def section(title):
            content.add_widget(MDLabel(text=title, theme_text_color="Custom",
                                        text_color=TEXT_MUTE, font_style="Caption",
                                        size_hint_y=None, height=dp(22), bold=True))

        def row(label, value, color=None):
            r = MDBoxLayout(orientation="horizontal", size_hint_y=None,
                            height=dp(24))
            r.add_widget(MDLabel(text=label, theme_text_color="Custom",
                                  text_color=TEXT_DIM, font_style="Body2",
                                  size_hint_x=0.42))
            r.add_widget(MDLabel(
                text=str(value if value not in (None, "") else "—"),
                theme_text_color="Custom", text_color=color or TEXT,
                font_style="Body2", bold=True, halign="right"))
            content.add_widget(r)

        section("IDENTITY")
        row("Name", conn.get("name",""))
        row("Host", conn.get("host",""))
        row("Port", conn.get("port",3389))
        row("Username", conn.get("username",""))
        row("Group", conn.get("group",""))

        section("SYSTEM")
        row("Processor", info.get("cpu_name","—"))
        row("Cores", f"{info.get('cores','—')}C / {info.get('threads','—')}T")
        row("RAM", f"{info.get('ram_gb','—')} GB")
        row("OS", info.get("os","—"))
        row("Hostname", info.get("hostname","—"))

        section("NETWORK")
        lat = st.get("latency"); jit = st.get("jitter")
        if alive is True: row("Status", "Online", GREEN)
        elif alive is False: row("Status", "Offline", RED)
        else: row("Status", "Unknown", TEXT_MUTE)
        row("Ping", f"{lat} ms" if lat is not None else "—")
        row("Jitter", f"±{jit} ms" if jit is not None else "—")
        row("Last check", st.get("last") or "—")

        if alive is False and st.get("error"):
            section("REASON")
            content.add_widget(MDLabel(text=st["error"],
                                        theme_text_color="Custom",
                                        text_color=RED, font_style="Caption",
                                        size_hint_y=None, height=dp(56)))

        dlg = MDDialog(title=f"Info — {conn.get('name','')}",
                       type="custom", content_cls=content,
                       buttons=[MDFlatButton(text="CLOSE",
                                              on_release=lambda x: dlg.dismiss())])
        dlg.open()

    def open_reason_dialog(self, conn):
        st = self.status_by_id.get(conn["id"], {})
        alive = st.get("alive")
        err = st.get("error")

        content = MDBoxLayout(orientation="vertical", spacing=dp(6),
                               size_hint_y=None, padding=[dp(4)]*4)
        content.bind(minimum_height=content.setter("height"))

        if alive is True:
            lat = st.get("latency")
            content.add_widget(MDLabel(text="Connection is healthy.",
                                        theme_text_color="Custom",
                                        text_color=GREEN, font_style="Subtitle1",
                                        size_hint_y=None, height=dp(28)))
            content.add_widget(MDLabel(text=f"Server responded in {lat} ms.",
                                        theme_text_color="Custom",
                                        text_color=TEXT_DIM, font_style="Body2",
                                        size_hint_y=None, height=dp(24)))
        elif alive is False:
            content.add_widget(MDLabel(text="Why it failed:",
                                        theme_text_color="Custom",
                                        text_color=TEXT_DIM, font_style="Caption",
                                        size_hint_y=None, height=dp(22)))
            box = MDCard(md_bg_color=SURFACE, radius=[dp(10)],
                          size_hint_y=None, height=dp(80),
                          padding=dp(12), elevation=0)
            box.add_widget(MDLabel(text=err or "Unknown error",
                                    theme_text_color="Custom", text_color=RED,
                                    font_style="Body2"))
            content.add_widget(box)

            content.add_widget(MDLabel(text="Possible causes:",
                                        theme_text_color="Custom",
                                        text_color=TEXT_DIM, font_style="Caption",
                                        size_hint_y=None, height=dp(24)))

            e_low = (err or "").lower()
            if "timeout" in e_low:
                hints = ["• Server offline or sleeping",
                         "• Firewall blocks port 3389",
                         "• ISP blocks outbound RDP",
                         "• Wrong IP address"]
            elif "refused" in e_low:
                hints = ["• RDP service not running",
                         "• RDP disabled in System Properties",
                         "• Firewall blocking the port"]
            elif "dns" in e_low or "resolve" in e_low:
                hints = ["• Hostname misspelled",
                         "• DNS server unreachable",
                         "• Try the IP address directly"]
            else:
                hints = ["• Check the host and port",
                         "• Verify network connectivity",
                         "• Check server firewall rules"]

            for h in hints:
                content.add_widget(MDLabel(text=h, theme_text_color="Custom",
                                            text_color=TEXT, font_style="Caption",
                                            size_hint_y=None, height=dp(22),
                                            padding=[dp(10), 0]))

        dlg = MDDialog(title=f"Reason — {conn.get('name','')}",
                       type="custom", content_cls=content,
                       buttons=[MDFlatButton(text="CLOSE",
                                              on_release=lambda x: dlg.dismiss())])
        dlg.open()

    def open_report_dialog(self, results):
        online = sum(1 for r in results if r["alive"] is True)
        offline = sum(1 for r in results if r["alive"] is False)

        outer = MDBoxLayout(orientation="vertical", spacing=dp(8),
                             size_hint_y=None, height=dp(440),
                             padding=[dp(4)]*4)
        outer.bind(minimum_height=outer.setter("height"))
        outer.add_widget(MDLabel(
            text=f"● {online} online   ● {offline} offline   ({len(results)} total)",
            theme_text_color="Custom", text_color=TEXT,
            font_style="Subtitle2", size_hint_y=None, height=dp(28)))

        scroll = MDScrollView(size_hint_y=None, height=dp(370))
        inner = MDBoxLayout(orientation="vertical", spacing=dp(8),
                             size_hint_y=None, padding=[dp(2)]*4)
        inner.bind(minimum_height=inner.setter("height"))

        for r in results:
            card = MDCard(orientation="vertical", size_hint_y=None,
                          height=dp(90), radius=[dp(10)],
                          md_bg_color=SURFACE, elevation=0,
                          padding=dp(10), spacing=dp(2))
            row = MDBoxLayout(orientation="horizontal", size_hint_y=None,
                              height=dp(24))
            dot_color = GREEN if r["alive"] is True else RED
            row.add_widget(MDLabel(text="●", theme_text_color="Custom",
                                    text_color=dot_color, font_style="H6",
                                    size_hint_x=None, width=dp(22)))
            row.add_widget(MDLabel(text=r["name"],
                                    theme_text_color="Custom",
                                    text_color=TEXT, font_style="Subtitle1",
                                    bold=True))
            row.add_widget(MDLabel(text=r["host"],
                                    theme_text_color="Custom",
                                    text_color=TEXT_DIM, font_style="Caption",
                                    halign="right"))
            card.add_widget(row)

            if r["alive"] is True:
                card.add_widget(MDLabel(text=f"✓ Online  ·  {r.get('latency')} ms",
                                         theme_text_color="Custom",
                                         text_color=GREEN, font_style="Caption",
                                         size_hint_y=None, height=dp(22)))
            else:
                card.add_widget(MDLabel(text=f"✗ {r.get('error') or 'Unknown'}",
                                         theme_text_color="Custom",
                                         text_color=RED, font_style="Caption",
                                         size_hint_y=None, height=dp(44),
                                         shorten=True))
            inner.add_widget(card)

        scroll.add_widget(inner)
        outer.add_widget(scroll)

        dlg = MDDialog(title="Connection Report", type="custom",
                       content_cls=outer,
                       buttons=[MDFlatButton(text="CLOSE",
                                              on_release=lambda x: dlg.dismiss())])
        dlg.open()

    def open_add_dialog(self):
        self.open_edit_dialog(None)

    def open_edit_dialog(self, conn):
        conn = conn or {}
        content = MDBoxLayout(orientation="vertical", spacing=dp(6),
                               size_hint_y=None, padding=[dp(4)]*4)
        content.bind(minimum_height=content.setter("height"))

        fields = {}
        def mk(label, key, default="", password=False):
            f = MDTextField(hint_text=label,
                            text=str(conn.get(key, default) or ""),
                            mode="rectangle", size_hint_y=None,
                            height=dp(54), password=password)
            content.add_widget(f)
            fields[key] = f

        mk("Name", "name")
        mk("Host / IP", "host")
        mk("Port", "port", "3389")
        mk("Username", "username")
        mk("Password", "password", password=True)
        mk("Group", "group", "Default")
        mk("Resolution", "resolution", "1920x1080")

        dlg_ref = {"dlg": None}

        def save(_):
            n = fields["name"].text.strip()
            h = fields["host"].text.strip()
            if not n or not h:
                self.snack("Name and Host are required"); return
            try: p = int(fields["port"].text or "3389")
            except ValueError:
                self.snack("Port must be a number"); return

            data = {
                "name": n, "host": h, "port": p,
                "username": fields["username"].text.strip(),
                "password": fields["password"].text,
                "group": fields["group"].text.strip() or "Default",
                "resolution": fields["resolution"].text.strip() or "1920x1080",
                "fullscreen": True, "drives": True, "save_password": True,
            }
            if conn.get("id"):
                data["id"] = conn["id"]
                if "sysinfo" in conn: data["sysinfo"] = conn["sysinfo"]
                for i, c in enumerate(self.connections):
                    if c["id"] == conn["id"]:
                        self.connections[i] = data; break
            else:
                data["id"] = str(uuid.uuid4())
                self.connections.append(data)
                self.status_by_id[data["id"]] = {
                    "alive": None, "latency": None, "jitter": None,
                    "min": None, "max": None, "last": None, "error": None,
                }
            self._save()
            self._refresh_home()
            if dlg_ref["dlg"]: dlg_ref["dlg"].dismiss()
            self.snack("Saved")
            self._executor.submit(self._probe, data["id"])

        dlg = MDDialog(
            title="Edit Connection" if conn.get("id") else "New Connection",
            type="custom", content_cls=content,
            buttons=[
                MDFlatButton(text="CANCEL", on_release=lambda x: dlg.dismiss()),
                MDRaisedButton(text="SAVE", on_release=save),
            ])
        dlg.open()
        dlg_ref["dlg"] = dlg

    def open_sysinfo_dialog(self, conn):
        info = conn.get("sysinfo") or {}
        content = MDBoxLayout(orientation="vertical", spacing=dp(6),
                               size_hint_y=None, padding=[dp(4)]*4)
        content.bind(minimum_height=content.setter("height"))
        content.add_widget(MDLabel(
            text="Open Task Manager inside the RDP session and copy the values.",
            theme_text_color="Custom", text_color=TEXT_DIM,
            font_style="Caption", size_hint_y=None, height=dp(48)))

        fields = {}
        def mk(label, key, default=""):
            f = MDTextField(hint_text=label,
                            text=str(info.get(key, default) or ""),
                            mode="rectangle", size_hint_y=None, height=dp(54))
            content.add_widget(f); fields[key] = f

        mk("CPU name", "cpu_name")
        mk("Cores (physical)", "cores")
        mk("Threads (logical)", "threads")
        mk("RAM (GB)", "ram_gb")
        mk("Operating System", "os")
        mk("Hostname", "hostname")

        dlg_ref = {"dlg": None}

        def save(_):
            try:
                new_info = {
                    "cpu_name": fields["cpu_name"].text.strip(),
                    "cores": int(fields["cores"].text or 0),
                    "threads": int(fields["threads"].text or 0),
                    "ram_gb": float(fields["ram_gb"].text or 0),
                    "os": fields["os"].text.strip(),
                    "hostname": fields["hostname"].text.strip(),
                }
            except ValueError:
                self.snack("Cores/Threads/RAM must be numbers"); return
            conn["sysinfo"] = new_info
            self._save(); self._refresh_home()
            if dlg_ref["dlg"]: dlg_ref["dlg"].dismiss()
            self.snack("Sysinfo saved")

        dlg = MDDialog(title=f"Sysinfo — {conn.get('name','')}",
                       type="custom", content_cls=content,
                       buttons=[
                           MDFlatButton(text="CANCEL",
                                         on_release=lambda x: dlg.dismiss()),
                           MDRaisedButton(text="SAVE", on_release=save),
                       ])
        dlg.open()
        dlg_ref["dlg"] = dlg


if __name__ == "__main__":
    RDPManagerMobile().run()
