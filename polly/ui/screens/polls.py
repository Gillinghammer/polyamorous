from __future__ import annotations

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Header, Footer, DataTable, Static, ListView, ListItem, Label, RichLog, Collapsible, Button, Markdown
from textual.containers import Vertical, Horizontal, Container
from textual.message import Message
import webbrowser

from ...config import Config
from ...db import Database
from ...services.polymarket import IngestionService
from ...services.research import ResearchService
from ...services.trading_paper import PaperTradingGateway
from ...services.portfolio import PortfolioService
from ..widgets.filters import FiltersBar
from .dashboard import DashboardScreen


class ResearchStatusUpdate(Message):
    """Message sent when research status updates."""
    def __init__(self, poll_id: str, status: str) -> None:
        self.poll_id = poll_id
        self.status = status
        super().__init__()


class ResearchComplete(Message):
    """Message sent when research completes."""
    def __init__(self, poll_id: str) -> None:
        self.poll_id = poll_id
        super().__init__()


class PollsScreen(Screen):
    BINDINGS = [
        ("r", "research", "Research"),
        ("y", "accept_recommendation", "Accept"),
        ("n", "reject_recommendation", "Reject"),
        ("t", "toggle_rationale", "Rationale"),
        ("e", "enter", "Enter"),
        ("p", "archive", "Archive"),
        ("o", "open_url", "Open URL"),
        ("c", "toggle_citations", "Citations"),
        ("d", "dashboard", "Dashboard"),
        ("i", "filter_inbox", "Inbox"),
        ("ctrl+r", "filter_reviewed", "Reviewed"),
        ("ctrl+e", "filter_entered", "Entered"),
        ("ctrl+a", "filter_archived", "Archived"),
        ("ctrl+c", "filter_closed", "Closed"),
        ("q", "app.quit", "Quit"),
    ]

    def __init__(self, cfg: Config) -> None:
        super().__init__()
        self.cfg = cfg
        self.db = Database(cfg.db_path)
        self.ingest = IngestionService(cfg, self.db)
        self.research = ResearchService(cfg, self.db)
        self.trading = PaperTradingGateway(self.db)
        self.portfolio = PortfolioService(self.db)
        # Filters state
        self._filter_view: str = "inbox"
        self._filter_open_only: bool = True
        # Background research state
        self._active_research: dict[str, bool] = {}  # poll_id -> is_researching

    def compose(self) -> ComposeResult:
        yield Header()
        with Container():
            yield FiltersBar()
            with Horizontal():
                with Vertical():
                    yield Static("Polls", id="title")
                    table = DataTable(id="polls")
                    table.add_columns("Ends", "Cat", "Res", "Ent", "Liq", "Question", "Poll ID")
                    yield table
                with Vertical(id="details-pane"):
                    yield Static("Details", id="details-title")
                    # Recommendation box pinned to the top
                    with Horizontal(id="recommendation-row"):
                        yield Static("Research: (none)", id="research-summary")
                        yield Button("Accept", id="accept-btn")
                        yield Button("Reject", id="reject-btn")
                    # Compact poll header
                    with Horizontal(id="poll-header"):
                        yield Static("", id="poll-question")
                        yield Static("", id="poll-domain")
                        yield Button("Open", id="open-btn")
                    yield Static("", id="research-status")
                    # Activity log (open by default; remains for later review)
                    with Collapsible(title="Activity", id="activity", collapsed=False):
                        yield RichLog(id="research-log")
                    # Collapsible rationale section
                    with Collapsible(title="Rationale", id="rationale", collapsed=False):
                        yield Markdown("", id="rationale-body")
                    with Collapsible(title="Citations Web(0) X(0)", id="citations", collapsed=False):
                        yield ListView(id="citations-list")
                    # Outcomes at the bottom
                    out = DataTable(id="outcomes")
                    out.add_columns("Outcome", "Bid", "Ask", "Mid", "Size$", "Payout$", "Profit$")
                    yield out
        yield Footer()

    def on_mount(self) -> None:
        self._update_filter_indicator()
        # Ensure sections start opened and pinned at top by avoiding extra vertical stretchers
        try:
            act = self.query_one("#activity", Collapsible)
            act.display = True
            act.collapsed = False
        except Exception:
            pass
        try:
            cit = self.query_one("#citations", Collapsible)
            cit.collapsed = False
        except Exception:
            pass
        try:
            rat = self.query_one("#rationale", Collapsible)
            rat.collapsed = False
        except Exception:
            pass
        self.refresh_polls()

    def refresh_polls(self) -> None:
        # Fetch top 50 non-sports open markets for richer triage
        ingested = self.ingest.ingest_markets(open_only=True, since_hours=None, top_n=50)
        table = self.query_one("#polls", DataTable)
        table.clear()
        # Reflect ingest result for user clarity
        title = self.query_one("#title", Static)
        if ingested == 0:
            title.update("Inbox — No markets fetched (check network/API). Press Refresh to retry.")
        else:
            title.update("Inbox — Unreviewed polls")

        with self.db.as_conn() as conn:
            # Build dynamic filters
            import time as _t
            now = int(_t.time())
            where = ["1=1"]
            params: list[object] = []
            if self._filter_open_only:
                where.append("p.status='active'")
            if self._filter_view == "inbox":
                where += [
                    "p.archived=0",
                    "NOT EXISTS (SELECT 1 FROM research r WHERE r.poll_id=p.poll_id)",
                    "NOT EXISTS (SELECT 1 FROM trades t WHERE t.poll_id=p.poll_id AND t.status='open')",
                ]
            elif self._filter_view == "reviewed":
                where += [
                    "p.archived=0",
                    "EXISTS (SELECT 1 FROM research r WHERE r.poll_id=p.poll_id)",
                    "NOT EXISTS (SELECT 1 FROM trades t WHERE t.poll_id=p.poll_id AND t.status='open')",
                ]
            elif self._filter_view == "entered":
                where.append("EXISTS (SELECT 1 FROM trades t WHERE t.poll_id=p.poll_id AND t.status='open')")
            elif self._filter_view == "archived":
                where.append("p.archived=1")
            elif self._filter_view == "closed":
                where.append("EXISTS (SELECT 1 FROM trades t WHERE t.poll_id=p.poll_id AND t.status='closed')")

            sql = (
                "SELECT p.poll_id, p.question, p.category, p.end_time, p.status "
                "FROM polls p WHERE " + " AND ".join(where) + " ORDER BY p.end_time ASC LIMIT 500"
            )
            cur = conn.execute(sql, params)
            for row in cur.fetchall():
                # Compute ends label and severity class
                from ...utils import format_time_until

                ends_label, sev = format_time_until(int(row[3] or 0))
                category = row[2] or ""
                res = "✓" if (row[4] or "").lower() != "active" else "·"
                ent = "·"  # computed later if needed
                liq = ""  # placeholder until we store liquidity
                question = row[1]
                poll_id = row[0]
                # DataTable in current Textual doesn't accept classes on add_row; color via text for now
                table.add_row(ends_label, category, res, ent, liq, question, poll_id)
        # Select first row and update details
        if table.row_count:
            table.cursor_type = "row"
            table.move_cursor(row=0, column=0)
            self._update_details()

    def action_research(self) -> None:
        table = self.query_one("#polls", DataTable)
        if table.cursor_row is None:
            return
        row_key = table.cursor_row
        try:
            values = table.get_row(row_key)  # row_key variant
        except Exception:
            values = table.get_row_at(int(row_key))  # index variant
        # Expect the expanded columns; support old schema fallback
        if len(values) >= 7:
            _, _, _, _, _, question, poll_id = values
        else:
            poll_id, question, _ = values
        
        poll_id = str(poll_id)
        question = str(question)
        
        # Check if already researching this poll
        if self._active_research.get(poll_id, False):
            return
            
        # Start background research
        self._active_research[poll_id] = True
        self._update_research_status(poll_id, "Researching...")
        try:
            log = self.query_one("#research-log", RichLog)
            log.write(f"Starting research: {question}")
        except Exception:
            pass
        self.run_worker(lambda: self._research_worker(poll_id, question), thread=True, exclusive=False)

    def _research_worker(self, poll_id: str, question: str) -> None:
        def cb(msg: str) -> None:
            try:
                self.post_message(ResearchStatusUpdate(poll_id, msg))
            except Exception:
                pass
        
        try:
            self.research.run_research_stream(poll_id, question, callback=cb)
        except Exception as exc:
            self.post_message(ResearchStatusUpdate(poll_id, f"Error: {exc}"))
        finally:
            self.post_message(ResearchComplete(poll_id))

    def action_enter(self) -> None:
        table = self.query_one("#polls", DataTable)
        if table.cursor_row is None:
            return
        row_key = table.cursor_row
        try:
            values = table.get_row(row_key)
        except Exception:
            values = table.get_row_at(int(row_key))
        if len(values) >= 7:
            _, _, _, _, _, _, poll_id = values
        else:
            poll_id, _, _ = values
        outcome_id = self.portfolio._select_primary_outcome(str(poll_id))
        metrics = self.portfolio.compute_metrics()
        size = round(0.10 * metrics.available_cash, 2)
        from ..dialogs.confirm import ConfirmDialog
        message = f"Enter paper trade?\nAvailable: ${metrics.available_cash:,.2f}\nSize: ${size:,.2f} (10%)"

        def _after(result: bool | None) -> None:
            if result:
                if size > 0:
                    self.trading.place_order(poll_id=str(poll_id), outcome_id=outcome_id, side="buy", size_usdc=size)
                    self.refresh_polls()

        self.app.push_screen(ConfirmDialog(message), _after)

    def action_archive(self) -> None:
        table = self.query_one("#polls", DataTable)
        if table.cursor_row is None:
            return
        row_key = table.cursor_row
        try:
            values = table.get_row(row_key)
        except Exception:
            values = table.get_row_at(int(row_key))
        if len(values) >= 7:
            _, _, _, _, _, _, poll_id = values
        else:
            poll_id, _, _ = values
        with self.db.as_conn() as conn:
            conn.execute("UPDATE polls SET archived=1 WHERE poll_id=?", (str(poll_id),))
        self.refresh_polls()

    def action_open_url(self) -> None:
        poll = self._current_poll()
        if not poll:
            return
        webbrowser.open(poll["url"])  # type: ignore[index]

    def action_toggle_citations(self) -> None:
        lv = self.query_one("#citations-list", ListView)
        lv.display = not lv.display

    def action_dashboard(self) -> None:
        self.app.push_screen(DashboardScreen(self.cfg))

    def action_filter_inbox(self) -> None:
        self._filter_view = "inbox"
        self._update_filter_indicator()
        self.refresh_polls()

    def action_filter_reviewed(self) -> None:
        self._filter_view = "reviewed"
        self._update_filter_indicator()
        self.refresh_polls()

    def action_filter_entered(self) -> None:
        self._filter_view = "entered"
        self._update_filter_indicator()
        self.refresh_polls()

    def action_filter_archived(self) -> None:
        self._filter_view = "archived"
        self._update_filter_indicator()
        self.refresh_polls()

    def action_filter_closed(self) -> None:
        self._filter_view = "closed"
        self._update_filter_indicator()
        self.refresh_polls()

    def _update_filter_indicator(self) -> None:
        """Update the filter view indicator text."""
        view_names = {
            "inbox": "Inbox",
            "reviewed": "Reviewed", 
            "entered": "Entered",
            "archived": "Archived",
            "closed": "Closed"
        }
        current_view = view_names.get(self._filter_view, "Inbox")
        indicator = self.query_one("#filter-view-indicator", Static)
        indicator.update(f"View: {current_view} (i/r/e/a/c)")

    def _update_research_status(self, poll_id: str, status: str) -> None:
        """Update research status for a specific poll."""
        current_poll = self._current_poll()
        if current_poll and current_poll["poll_id"] == poll_id:
            status_widget = self.query_one("#research-status", Static)
            if status:
                status_widget.update(f"Status: {status}")
                status_widget.styles.color = "yellow"
                # ensure activity is visible when running
                try:
                    act = self.query_one("#activity", Collapsible)
                    act.display = True
                    act.collapsed = False
                except Exception:
                    pass
            else:
                status_widget.update("")
                status_widget.styles.color = "white"
                # keep activity for later review, but collapsed
                try:
                    act = self.query_one("#activity", Collapsible)
                    act.collapsed = True
                    act.display = True
                except Exception:
                    pass

    def _current_poll(self):
        table = self.query_one("#polls", DataTable)
        if table.cursor_row is None:
            return None
        row_key = table.cursor_row
        try:
            values = table.get_row(row_key)
        except Exception:
            values = table.get_row_at(int(row_key))
        if len(values) >= 7:
            poll_id = values[6]
        else:
            poll_id, _, _ = values
        with self.db.as_conn() as conn:
            cur = conn.execute("SELECT poll_id, question, url FROM polls WHERE poll_id=?", (str(poll_id),))
            row = cur.fetchone()
            return row

    def _update_details(self) -> None:
        poll = self._current_poll()
        if not poll:
            return
        # Update compact header
        try:
            q_text = str(poll["question"]) if poll["question"] else ""
            if len(q_text) > 90:
                q_text = q_text[:87] + "…"
            self.query_one("#poll-question", Static).update(q_text)
            from urllib.parse import urlparse
            parsed = urlparse(str(poll["url"]))
            self.query_one("#poll-domain", Static).update(parsed.netloc)
        except Exception:
            pass
        # Outcomes
        out = self.query_one("#outcomes", DataTable)
        out.clear()
        with self.db.as_conn() as conn:
            cur = conn.execute(
                "SELECT outcome_id, name, price FROM outcomes WHERE poll_id=? ORDER BY name ASC",
                (poll["poll_id"],),
            )
            outcomes = cur.fetchall()
            primary_mid = None
            # Determine primary outcome id to mark
            try:
                primary_outcome_id = self.portfolio._select_primary_outcome(str(poll["poll_id"]))
            except Exception:
                primary_outcome_id = None
            primary_name = None
            row_count = 0
            for row in outcomes:
                price = None if row[2] is None else float(row[2])
                if primary_mid is None and price is not None:
                    primary_mid = price
                # For now, show bid/ask as empty and mid as last price
                name = row[1]
                display_name = ("★ " + name) if primary_outcome_id and row[0] == primary_outcome_id else name
                if primary_outcome_id and row[0] == primary_outcome_id:
                    primary_name = name
                # Extend columns for size/payout/profit (to be filled after computing below)
                out.add_row(display_name, "", "", "" if price is None else f"{price:.3f}", "", "", "")
                row_count += 1
            out.display = row_count > 0
            # Latest research
            cur = conn.execute(
                "SELECT id, recommendation, confidence, position_size_pct, rationale FROM research WHERE poll_id=? ORDER BY completed_at DESC NULLS LAST LIMIT 1",
                (poll["poll_id"],),
            )
            r = cur.fetchone()
            if r:
                rec = r["recommendation"] or "?"
                conf = r["confidence"] if r["confidence"] is not None else 0
                sz = r["position_size_pct"] if r["position_size_pct"] is not None else 0
                # Compute money context from portfolio and primary outcome mid
                metrics = self.portfolio.compute_metrics()
                size_usd = round(float(sz) * float(metrics.available_cash), 2)
                shares = (size_usd / primary_mid) if (primary_mid and primary_mid > 0) else None
                max_payout = (shares * 1.0) if shares is not None else None
                max_profit = (max_payout - size_usd) if max_payout is not None else None
                # Compact summary with explicit side (remove redundant payout text; numbers shown elsewhere)
                side_text = (primary_name or "?") if rec == "enter" else ""
                side_prefix = f"Enter {side_text}" if rec == "enter" else "Pass"
                summary = f"{side_prefix} • conf {conf:.2f} • size {sz:.2f}"
                # Update recommendation row visibility; hide buttons for pass
                rec_row = self.query_one("#recommendation-row", Horizontal)
                rec_row.display = True
                self.query_one("#research-summary", Static).update(summary)
                # Populate decision chips
                try:
                    self.query_one("#size-chip", Static).update(f"size $ {size_usd:,.2f}")
                except Exception:
                    pass
                try:
                    if max_payout is not None:
                        self.query_one("#payout-chip", Static).update(f"payout $ {max_payout:,.2f}")
                    else:
                        self.query_one("#payout-chip", Static).update("")
                except Exception:
                    pass
                try:
                    if max_profit is not None:
                        self.query_one("#profit-chip", Static).update(f"profit $ {max_profit:,.2f}")
                    else:
                        self.query_one("#profit-chip", Static).update("")
                except Exception:
                    pass
                # Fill outcomes row extra columns for primary outcome (size/payout/profit)
                try:
                    table = self.query_one("#outcomes", DataTable)
                    for idx in range(table.row_count):
                        row_vals = table.get_row_at(idx)
                        if isinstance(row_vals[0], str) and row_vals[0].startswith("★ "):
                            table.update_cell_at((idx, 4), f"{size_usd:,.2f}")  # Size$
                            table.update_cell_at((idx, 5), "" if max_payout is None else f"{max_payout:,.2f}")
                            table.update_cell_at((idx, 6), "" if max_profit is None else f"{max_profit:,.2f}")
                            break
                except Exception:
                    pass
                # Also populate rationale collapsible body (markdown)
                try:
                    rb = self.query_one("#rationale-body", Markdown)
                    rb.update((r["rationale"] or "").strip())
                except Exception:
                    pass
                # Show/hide action buttons based on recommendation
                try:
                    accept_btn = self.query_one("#accept-btn", Button)
                    reject_btn = self.query_one("#reject-btn", Button)
                    if rec == "enter":
                        # Update label with side for clarity
                        try:
                            accept_btn.label = f"Enter {side_text}"  # type: ignore[attr-defined]
                        except Exception:
                            pass
                        accept_btn.display = True
                        reject_btn.display = True
                    else:
                        accept_btn.display = False
                        reject_btn.display = False
                except Exception:
                    pass
                # citations
                cur2 = conn.execute(
                    "SELECT kind, title, url FROM citations WHERE research_id=?",
                    (r["id"],),
                )
                web_list = []
                x_list = []
                for c in cur2.fetchall():
                    (web_list if c["kind"] == "web" else x_list).append((c["title"] or c["url"], c["url"]))
                # Update citations header and list
                try:
                    citations_col = self.query_one("#citations", Collapsible)
                    citations_col.title = f"Citations Web({len(web_list)}) X({len(x_list)})"
                    citations_col.display = (len(web_list) + len(x_list)) > 0
                except Exception:
                    pass
                lv = self.query_one("#citations-list", ListView)
                lv.clear()
                # Cap list length and height to content
                max_links = 8
                items = (web_list + x_list)[:max_links]
                for title, url in items:
                    try:
                        from urllib.parse import urlparse
                        domain = urlparse(url).netloc or url
                    except Exception:
                        domain = url
                    label_text = f"{domain} — {title}"
                    item = ListItem(Label(label_text))
                    item.data = url  # type: ignore[attr-defined]
                    lv.append(item)
            else:
                # No research yet: keep rationale/citations collapsibles present but empty
                try:
                    self.query_one("#recommendation-row", Horizontal).display = False
                except Exception:
                    pass
                self.query_one("#research-summary", Static).update("Research: (none)")
                try:
                    col = self.query_one("#citations", Collapsible)
                    col.title = "Citations Web(0) X(0)"
                    col.display = False
                except Exception:
                    pass
                self.query_one("#citations-list", ListView).clear()
            
            # Update research status for current poll
            current_poll_id = poll["poll_id"]
            if self._active_research.get(current_poll_id, False):
                status_widget = self.query_one("#research-status", Static)
                status_widget.update("Status: Researching...")
                status_widget.styles.color = "yellow"
            else:
                status_widget = self.query_one("#research-status", Static)
                status_widget.update("")
                status_widget.styles.color = "white"

    def on_data_table_row_selected(self, _) -> None:  # cursor move isn't always emitted; handle selection
        self._update_details()


    # Filters wiring


    def on_switch_changed(self, event) -> None:
        if getattr(event.switch, 'id', '') == "filter-open-only":
            self._filter_open_only = bool(event.value)
            self.refresh_polls()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        # Open citation URL
        try:
            url = getattr(event.item, "data", None)  # type: ignore[attr-defined]
            if url:
                webbrowser.open(url)
        except Exception:
            pass

    def on_research_status_update(self, event: ResearchStatusUpdate) -> None:
        """Handle research status updates from background thread."""
        self._update_research_status(event.poll_id, event.status)
        try:
            log = self.query_one("#research-log", RichLog)
            if event.status:
                log.write(event.status)
        except Exception:
            pass

    def on_research_complete(self, event: ResearchComplete) -> None:
        """Handle research completion from background thread."""
        self._active_research.pop(event.poll_id, None)
        self._update_research_status(event.poll_id, "")
        self.refresh_polls()
        # Also refresh details panel to show new research results
        self._update_details()
        try:
            log = self.query_one("#research-log", RichLog)
            # Echo final summary line in the log for at-a-glance confirmation
            try:
                summary = self.query_one("#research-summary", Static).renderable  # type: ignore[attr-defined]
                log.write(f"Summary: {summary}")
            except Exception:
                log.write("Research complete.")
        except Exception:
            pass

    def action_toggle_rationale(self) -> None:
        try:
            col = self.query_one("#rationale", Collapsible)
            col.collapsed = not col.collapsed
        except Exception:
            pass

    def action_accept_recommendation(self) -> None:
        poll = self._current_poll()
        if not poll:
            return
        poll_id = str(poll["poll_id"])
        # Fetch latest research for sizing
        with self.db.as_conn() as conn:
            cur = conn.execute(
                "SELECT id, position_size_pct FROM research WHERE poll_id=? ORDER BY completed_at DESC NULLS LAST LIMIT 1",
                (poll_id,),
            )
            r = cur.fetchone()
        if not r:
            return
        pct = float(r["position_size_pct"] or 0.0)
        if pct <= 0:
            return
        metrics = self.portfolio.compute_metrics()
        size = round(pct * metrics.available_cash, 2)
        if size <= 0:
            return
        outcome_id = self.portfolio._select_primary_outcome(poll_id)
        self.trading.place_order(poll_id=poll_id, outcome_id=outcome_id, side="buy", size_usdc=size)
        self.refresh_polls()

    def action_reject_recommendation(self) -> None:
        poll = self._current_poll()
        if not poll:
            return
        with self.db.as_conn() as conn:
            conn.execute("UPDATE polls SET archived=1 WHERE poll_id=?", (str(poll["poll_id"]),))
        self.refresh_polls()


