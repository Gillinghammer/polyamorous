# Textual TUI Framework Guide

> **Note**: This guide is for reference only. If you need clarity or more information, use the Context7 MCP tool to fetch the latest documentation.

## Overview

Textual is a modern TUI (Terminal User Interface) framework for Python that enables building sophisticated terminal applications with a simple Python API. Perfect for our `poly` application.

## Installation

```bash
pip install textual>=0.40.0
```

## Basic App Structure

```python
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Static

class PolyApp(App):
    """Main Poly application."""
    
    # App metadata
    TITLE = "Poly"
    SUB_TITLE = "Polymarket Research & Paper Trading"
    
    def compose(self) -> ComposeResult:
        """Compose the UI."""
        yield Header()
        yield Static("Hello, Poly!")
        yield Footer()

if __name__ == "__main__":
    app = PolyApp()
    app.run()
```

## Essential Widgets for Phase 1

### 1. ListView - For Poll List

Display a scrollable list of polls:

```python
from textual.widgets import ListView, ListItem, Label

class PollsList(App):
    def compose(self) -> ComposeResult:
        yield ListView(
            ListItem(Label("Poll 1: Will candidate X win?")),
            ListItem(Label("Poll 2: Will GDP exceed 3%?")),
            ListItem(Label("Poll 3: Will inflation drop?")),
        )
    
    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle poll selection."""
        self.notify(f"Selected: {event.item}")
```

### 2. DataTable - For Market Data

Display tabular market data:

```python
from textual.widgets import DataTable

class MarketsTable(App):
    def compose(self) -> ComposeResult:
        yield DataTable()
    
    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_columns("Question", "Yes", "No", "Liquidity", "Days Left")
        table.add_rows([
            ("Will X win?", "0.62", "0.38", "$1.2M", "5"),
            ("GDP > 3%?", "0.45", "0.55", "$850K", "12"),
        ])
```

### 3. LoadingIndicator - For Research Progress

Show loading state during 20-40 minute research:

```python
from textual.widgets import LoadingIndicator

class ResearchView(App):
    def compose(self) -> ComposeResult:
        yield LoadingIndicator()
```

### 4. ProgressBar - For Research Progress

Show determinate or indeterminate progress:

```python
from textual.widgets import ProgressBar

class ResearchProgress(App):
    def compose(self) -> ComposeResult:
        # Indeterminate (when duration unknown)
        yield ProgressBar()
        
        # Determinate (when tracking rounds)
        yield ProgressBar(total=100, show_eta=True)
    
    def update_progress(self, completed):
        progress = self.query_one(ProgressBar)
        progress.update(progress=completed)
```

### 5. Static - For Text Display

Display research results:

```python
from textual.widgets import Static

class ResultsDisplay(App):
    def compose(self) -> ComposeResult:
        yield Static("Research Results", id="results")
    
    def update_results(self, text):
        self.query_one("#results", Static).update(text)
```

## Async Workers (Critical for Long Research)

**Essential for 20-40 minute research without blocking the UI:**

### Using @work Decorator

```python
from textual.app import App, ComposeResult
from textual.widgets import Static, Button, LoadingIndicator
from textual.worker import work
import asyncio

class ResearchApp(App):
    def compose(self) -> ComposeResult:
        yield Button("Start Research", id="start")
        yield Static("Status: Ready", id="status")
        yield LoadingIndicator(id="loading")
    
    def on_mount(self) -> None:
        # Hide loading indicator initially
        self.query_one("#loading").display = False
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "start":
            self.run_research()
    
    @work(exclusive=True)
    async def run_research(self) -> None:
        """Run long research in background."""
        status = self.query_one("#status", Static)
        loading = self.query_one("#loading", LoadingIndicator)
        
        # Show loading
        loading.display = True
        status.update("Status: Researching...")
        
        # Simulate long research (20-40 minutes in production)
        for round_num in range(1, 5):
            status.update(f"Status: Research Round {round_num}/4...")
            await asyncio.sleep(5)  # In production: actual Grok API call
        
        # Hide loading and show results
        loading.display = False
        status.update("Status: Research Complete!")
        self.notify("Research finished!", title="Complete")

if __name__ == "__main__":
    app = ResearchApp()
    app.run()
```

### Real-time Progress Updates

```python
from textual.app import App, ComposeResult
from textual.widgets import Static, ProgressBar
from textual.worker import work
import asyncio

class ProgressiveResearch(App):
    def compose(self) -> ComposeResult:
        yield Static("Research Progress", id="title")
        yield Static("Initializing...", id="status")
        yield ProgressBar(total=100, id="progress")
    
    def on_mount(self) -> None:
        self.start_research()
    
    @work(exclusive=True)
    async def start_research(self) -> None:
        """Async research with progress updates."""
        status = self.query_one("#status", Static)
        progress = self.query_one("#progress", ProgressBar)
        
        research_steps = [
            "Analyzing poll question...",
            "Searching web for recent news...",
            "Searching X for expert opinions...",
            "Cross-referencing sources...",
            "Synthesizing findings...",
        ]
        
        for i, step in enumerate(research_steps):
            status.update(step)
            progress.update(progress=(i + 1) * 20)
            await asyncio.sleep(2)  # Simulated work
        
        status.update("Research complete!")
        self.notify("Analysis finished", title="Success")

if __name__ == "__main__":
    app = ProgressiveResearch()
    app.run()
```

## Layouts and Containers

### Grid Layout for Dashboard

```python
from textual.app import App, ComposeResult
from textual.containers import Grid
from textual.widgets import Static

class DashboardApp(App):
    CSS = """
    Grid {
        grid-size: 2 2;
        grid-gutter: 1;
    }
    Static {
        height: 10;
        border: solid green;
        content-align: center middle;
    }
    """
    
    def compose(self) -> ComposeResult:
        yield Grid(
            Static("Active Positions\n5"),
            Static("Win Rate\n80%"),
            Static("Total Profit\n$1,250"),
            Static("Projected APR\n45%"),
        )

if __name__ == "__main__":
    app = DashboardApp()
    app.run()
```

### Vertical/Horizontal Containers

```python
from textual.containers import Vertical, Horizontal
from textual.widgets import Button

class LayoutExample(App):
    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("Poll Details")
            with Horizontal():
                yield Button("Enter Trade")
                yield Button("Pass")
```

## Reactive Attributes

Update UI when data changes:

```python
from textual.reactive import reactive
from textual.widgets import Static

class LiveMetrics(Static):
    """Widget that auto-updates when metrics change."""
    
    win_rate = reactive(0.0)
    total_profit = reactive(0.0)
    
    def watch_win_rate(self, win_rate: float) -> None:
        """Called when win_rate changes."""
        self.update(f"Win Rate: {win_rate:.1%}")
    
    def watch_total_profit(self, profit: float) -> None:
        """Called when profit changes."""
        self.update(f"Total Profit: ${profit:,.2f}")

# Usage in app
metrics = self.query_one(LiveMetrics)
metrics.win_rate = 0.85  # Automatically updates display
metrics.total_profit = 1250.00
```

## Event Handling

```python
from textual.app import App, ComposeResult
from textual.widgets import Button, Static

class EventApp(App):
    def compose(self) -> ComposeResult:
        yield Button("Research Poll", id="research")
        yield Static("", id="output")
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button clicks."""
        if event.button.id == "research":
            self.start_research()
    
    def on_key(self, event) -> None:
        """Handle keyboard shortcuts."""
        if event.key == "q":
            self.exit()
        elif event.key == "r":
            self.start_research()
```

## Styling with CSS

Create a `.tcss` file:

```css
/* poly.tcss */
Screen {
    background: $surface;
}

Header {
    background: $primary;
}

ListView {
    border: solid $accent;
    height: 60%;
}

ListItem:hover {
    background: $accent 20%;
}

Button {
    margin: 1;
}

#research-status {
    color: $success;
    text-align: center;
}

#loading {
    align: center middle;
}
```

Load in your app:

```python
class PolyApp(App):
    CSS_PATH = "poly.tcss"
```

## Complete Example: Research App

```python
from textual.app import App, ComposeResult
from textual.containers import Container, Vertical, Horizontal
from textual.widgets import Header, Footer, Static, Button, LoadingIndicator
from textual.worker import work
import asyncio

class PolyResearchApp(App):
    """Polymarket research application."""
    
    TITLE = "Poly Research"
    
    CSS = """
    Container {
        padding: 1;
        align: center middle;
    }
    #status {
        width: 100%;
        text-align: center;
        margin: 1;
    }
    #loading {
        margin: 1;
    }
    Button {
        margin: 1;
    }
    """
    
    def compose(self) -> ComposeResult:
        yield Header()
        with Container():
            yield Static("Select a poll to research", id="poll-name")
            yield Static("Status: Ready", id="status")
            yield LoadingIndicator(id="loading")
            with Horizontal():
                yield Button("Start Research", id="start", variant="primary")
                yield Button("Cancel", id="cancel", variant="error")
        yield Footer()
    
    def on_mount(self) -> None:
        # Hide loading initially
        self.query_one("#loading", LoadingIndicator).display = False
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "start":
            self.run_research()
        elif event.button.id == "cancel":
            self.workers.cancel_all()
            self.query_one("#status", Static).update("Status: Cancelled")
    
    @work(exclusive=True)
    async def run_research(self) -> str:
        """Run Grok research in background (20-40 min)."""
        status = self.query_one("#status", Static)
        loading = self.query_one("#loading", LoadingIndicator)
        
        loading.display = True
        
        # Simulated research rounds (in production: actual Grok API)
        rounds = [
            "Analyzing poll question...",
            "Searching web for recent news...",
            "Searching X for expert insights...",
            "Cross-referencing sources...",
            "Identifying information asymmetries...",
            "Synthesizing final prediction...",
        ]
        
        for i, round_desc in enumerate(rounds, 1):
            status.update(f"Round {i}/{len(rounds)}: {round_desc}")
            await asyncio.sleep(3)  # Production: actual API calls
        
        loading.display = False
        status.update("Status: Research Complete!")
        
        return "Research finished successfully"

if __name__ == "__main__":
    app = PolyResearchApp()
    app.run()
```

## Key Patterns for Phase 1

### 1. Non-Blocking Long Operations

**Always use `@work` decorator for operations > 1 second:**

```python
@work(exclusive=True)
async def long_operation(self) -> None:
    await asyncio.sleep(10)
    # Your long-running code here
```

### 2. Real-time UI Updates from Workers

```python
@work(exclusive=True)
async def research_worker(self) -> None:
    for i in range(100):
        # Update UI from worker (thread-safe)
        self.call_from_thread(
            self.query_one("#progress").update,
            progress=i
        )
        await asyncio.sleep(0.1)
```

### 3. Handle Worker Completion

```python
def on_button_pressed(self, event: Button.Pressed) -> None:
    worker = self.run_research()
    worker.finished.connect(self.on_research_finished)

def on_research_finished(self, result: str) -> None:
    """Called when research completes."""
    self.notify(result, title="Research Complete")
```

### 4. Streaming Updates Pattern

```python
from textual.message import Message

class ResearchUpdate(Message):
    """Message sent during research progress."""
    def __init__(self, round: int, activity: str):
        self.round = round
        self.activity = activity
        super().__init__()

@work(exclusive=True)
async def run_grok_research(self) -> None:
    """Research with streaming updates."""
    for round_num in range(1, 5):
        # Post message to update UI
        self.post_message(
            ResearchUpdate(round_num, f"Searching round {round_num}")
        )
        
        # Actual research work
        await asyncio.sleep(5)

def on_research_update(self, message: ResearchUpdate) -> None:
    """Handle research progress updates."""
    status = self.query_one("#status")
    status.update(f"Round {message.round}: {message.activity}")
```

## Querying Widgets

```python
# By ID
status = self.query_one("#status", Static)

# By type
all_buttons = self.query(Button)

# First match
first_button = self.query_one(Button)

# Check if exists
if self.query("#optional-widget"):
    widget = self.query_one("#optional-widget")
```

## Dynamic Widget Management

```python
# Mount new widgets
new_widget = Static("New content")
await self.mount(new_widget)

# Remove widgets
widget = self.query_one("#removable")
widget.remove()

# Show/hide without removing
widget.display = False  # Hide
widget.display = True   # Show
```

## Key Bindings

```python
class PolyApp(App):
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("r", "refresh", "Refresh"),
        ("d", "dashboard", "Dashboard"),
        ("escape", "back", "Back"),
    ]
    
    def action_quit(self) -> None:
        self.exit()
    
    def action_refresh(self) -> None:
        self.refresh_markets()
    
    def action_dashboard(self) -> None:
        self.push_screen(DashboardScreen())
```

## Screens (Multi-View Navigation)

```python
from textual.screen import Screen

class PollsListScreen(Screen):
    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("Polls List")
        yield Footer()

class ResearchScreen(Screen):
    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("Research View")
        yield Footer()

class PolyApp(App):
    def on_mount(self) -> None:
        # Start with polls list
        self.push_screen(PollsListScreen())
    
    def show_research(self, poll_id: str) -> None:
        # Navigate to research screen
        self.push_screen(ResearchScreen())
    
    def go_back(self) -> None:
        # Pop current screen
        self.pop_screen()
```

## Best Practices for Phase 1

### 1. Always Use Async for Long Operations

```python
# ✅ Good - Non-blocking
@work(exclusive=True)
async def fetch_markets(self) -> None:
    markets = await get_polymarket_data()
    self.update_ui(markets)

# ❌ Bad - Blocks UI
def fetch_markets(self) -> None:
    markets = get_polymarket_data()  # UI freezes
    self.update_ui(markets)
```

### 2. Show Progress for Long Tasks

```python
@work(exclusive=True)
async def long_research(self) -> None:
    progress = self.query_one(ProgressBar)
    status = self.query_one(Static)
    
    for i in range(100):
        status.update(f"Processing {i}%...")
        progress.update(progress=i)
        await asyncio.sleep(0.1)
```

### 3. Handle Cancellation

```python
@work(exclusive=True)
async def research(self) -> None:
    for round in range(10):
        # Check if cancelled
        if self.workers[0].is_cancelled:
            return "Cancelled"
        
        await asyncio.sleep(5)
    
    return "Complete"
```

### 4. Update UI Thread-Safe

```python
@work(thread=True)  # Using threads instead of async
def threaded_work(self) -> None:
    result = expensive_computation()
    
    # Thread-safe UI update
    self.call_from_thread(
        self.query_one("#result").update,
        result
    )
```

## Complete Phase 1 Example

```python
from textual.app import App, ComposeResult
from textual.containers import Container, Vertical, Horizontal
from textual.widgets import Header, Footer, Static, Button, ListView, ListItem, Label, LoadingIndicator
from textual.worker import work
from textual.screen import Screen
import asyncio

class PollsListScreen(Screen):
    """Main screen showing poll list."""
    
    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(
            Static("Top 20 Liquid Non-Sports Polls", id="title"),
            ListView(
                ListItem(Label("Poll 1: Will candidate X win? | Yes: 0.62 | No: 0.38 | 5d")),
                ListItem(Label("Poll 2: GDP > 3%? | Yes: 0.45 | No: 0.55 | 12d")),
                ListItem(Label("Poll 3: Inflation drop? | Yes: 0.58 | No: 0.42 | 8d")),
                id="polls-list"
            ),
        )
        yield Footer()
    
    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """User selected a poll to research."""
        self.app.push_screen(ResearchScreen())

class ResearchScreen(Screen):
    """Screen for running research."""
    
    BINDINGS = [("escape", "back", "Back")]
    
    def compose(self) -> ComposeResult:
        yield Header()
        with Container():
            yield Static("Researching: Will candidate X win?", id="poll-question")
            yield Static("Status: Initializing...", id="status")
            yield LoadingIndicator(id="loading")
            yield Static("", id="results")
            with Horizontal():
                yield Button("Cancel", id="cancel", variant="error")
        yield Footer()
    
    def on_mount(self) -> None:
        # Start research automatically
        self.run_deep_research()
    
    @work(exclusive=True)
    async def run_deep_research(self) -> None:
        """Run 20-40 minute Grok research."""
        status = self.query_one("#status", Static)
        results = self.query_one("#results", Static)
        
        # Simulated research (in production: Grok API streaming)
        rounds = [
            "Analyzing poll context...",
            "Searching web for recent developments...",
            "Searching X for expert opinions...",
            "Cross-referencing multiple sources...",
            "Identifying market blind spots...",
            "Synthesizing final prediction...",
        ]
        
        for i, activity in enumerate(rounds, 1):
            status.update(f"Round {i}/{len(rounds)}: {activity}")
            await asyncio.sleep(3)  # Production: actual Grok streaming
            
            # Show interim findings
            results.update(f"Finding {i}: Some insight from research...")
        
        # Final results
        status.update("Status: Complete!")
        results.update(
            "PREDICTION: YES (72% probability)\n"
            "CONFIDENCE: 85%\n"
            "KEY FINDING: Market underestimates X factor...\n"
            "RECOMMENDATION: ENTER at current odds"
        )
        
        self.notify("Research complete!", title="Success")
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.workers.cancel_all()
    
    def action_back(self) -> None:
        self.app.pop_screen()

class PolyApp(App):
    """Main Poly application."""
    
    TITLE = "Poly"
    SUB_TITLE = "Polymarket Research & Paper Trading"
    
    def on_mount(self) -> None:
        self.push_screen(PollsListScreen())

if __name__ == "__main__":
    app = PolyApp()
    app.run()
```

## Debugging

Run with dev mode for live reload:

```bash
textual run --dev app.py
```

Access Textual console for logging:

```python
self.log("Debug message")
self.log(f"Variable: {value}")
```

## Resources

- [Textual Documentation](https://textual.textualize.io/)
- [Textual GitHub](https://github.com/textualize/textual)
- [Widget Gallery](https://textual.textualize.io/widget_gallery/)
- [Textual Discord](https://discord.gg/Enf6Z3qhVr)

