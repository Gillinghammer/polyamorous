"""Shared CSS for Poly TUI views.

Exported as CSS to be consumed by the App or individual views.
"""

CSS = """
Screen {
    background: #101217;
}

TabbedContent {
    padding: 1 2;
}

TabPane {
    padding: 1;
}

DataTable#polls-table {
    height: 24;
}

Static#polls-hint {
    color: #7a8699;
}

ProgressBar#research-progress {
    margin-bottom: 1;
}

Vertical#research-left {
    width: 2fr;   /* give left column 2x width */
    min-width: 40;
}

VerticalScroll#research-scroll {
    border: round #2c3340;
    padding: 1;
}

Vertical#research-right {
    width: 1fr;
    min-width: 30;
}

Static#research-status {
    color: #7a8699;
}

/* New clean decision container */
Vertical#decision-container {
    border: round #2c3340;
    background: #121722;
    padding: 1;
    margin-bottom: 1;
}
Vertical#decision-container.enter { 
    border: round #1f5f3a; 
    background: #0e1a14; 
}
Vertical#decision-container.neutral { 
    border: round #5a4f1a; 
    background: #1a1508; 
}
Vertical#decision-container.pass { 
    border: round #5f1f1f; 
    background: #1a0e0e; 
}

/* Metrics grid */
Horizontal#metrics-grid {
    margin: 1 0;
    height: auto;
}
Horizontal#metrics-grid Static {
    border: round #2c3340;
    padding: 0 1;
    margin-right: 1;
    background: #1e2633;
}

/* Position info */
Horizontal#position-info {
    margin: 1 0;
    height: auto;
}
Horizontal#position-info Static {
    border: round #2c3340;
    padding: 0 1;
    margin-right: 1;
    background: #1e2633;
}

/* Action buttons */
Horizontal#action-buttons {
    padding-top: 1;
    height: auto;
    dock: top;
    align-horizontal: right;
}
Horizontal#action-buttons > Button {
    margin-right: 2;
}

Markdown#research-summary {
    padding: 1;
    height: auto;
}

#citations-header {
    color: #9fb0c9;
    margin-top: 1;
}
Markdown#citations-list {
    padding: 0 1;
}

#edge-help {
    color: #9fb0c9;
}

/* Emphasize key numbers with colored chips inside markdown */
.chip {
    background: #1e2633;
    border: round #3a7bd5;
    padding: 0 1;
    text-style: bold;
}

DataTable#research-history {
    height: 24;
    border: round #2c3340;
    margin-top: 1;
}

#trade-bar {
    border: round #3a7bd5;
    background: #152033;
    color: #dbe9ff;
    padding: 1 2;
    text-style: bold;
    height: auto;
    margin-bottom: 1;
}

#active-flag {
    border: round #1f5f3a;
    color: #a7f3d0;
    padding: 0 1;
    text-style: bold;
}

DataTable#trades-table {
    height: 14;
}
"""


