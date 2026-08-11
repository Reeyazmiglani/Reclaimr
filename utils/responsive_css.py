"""Shared responsive + visual-polish CSS, layered on top of each page's
existing warm/dark theme CSS.

This is CSS-only: it adds mobile breakpoints, bigger tap targets, a
horizontal-scroll + fade cue for wide tables, subtle depth (rounded
corners / soft shadows) on cards, and a bit more weight contrast
between headers and body text. It intentionally reuses the "Warm
Chai" palette (cream, #C17F3E amber, #1B7F4F sage) and the same
`st.markdown(..., unsafe_allow_html=True)` mechanism every page
already uses for its own theme block, so it stacks on top rather than
replacing anything.

Usage: each entrypoint (app.py, pages/*.py) calls
`st.markdown(RESPONSIVE_CSS, unsafe_allow_html=True)` once, right
after injecting its own light/dark theme CSS.
"""

RESPONSIVE_CSS = """
<style>
/* ── General visual polish (all viewport sizes) ─────────────────────────── */

/* Subtle depth on cards / containers instead of flat rectangles. */
[data-testid="metric-container"],
[data-testid="stMetric"] {
    box-shadow: 0 1px 3px rgba(44,34,24,0.08), 0 1px 2px rgba(44,34,24,0.06) !important;
    transition: box-shadow 0.15s ease;
}
[data-testid="stDataFrame"],
[data-testid="stDataEditor"] {
    border-radius: 10px !important;
    overflow: hidden !important;
    box-shadow: 0 1px 4px rgba(44,34,24,0.10) !important;
}
details[data-testid="stExpander"] {
    border-radius: 10px !important;
    box-shadow: 0 1px 3px rgba(44,34,24,0.07) !important;
    overflow: hidden;
}
[data-testid="stForm"] {
    border-radius: 12px !important;
    box-shadow: 0 1px 4px rgba(44,34,24,0.08) !important;
}
div[data-baseweb="input"],
div[data-baseweb="textarea"],
div[data-baseweb="select"] > div:first-child {
    transition: box-shadow 0.15s ease;
}

/* Wide custom HTML tables (.orders-table / .etbl / .erp-tbl): let them
   scroll horizontally instead of silently clipping, with a soft fade
   cue pinned to the right edge indicating there's more to scroll. */
.orders-table, .etbl, .erp-tbl {
    display: block !important;
    overflow-x: auto !important;
    -webkit-overflow-scrolling: touch !important;
    border-radius: 8px !important;
    box-shadow: inset -18px 0 14px -14px rgba(44,34,24,0.16) !important;
}

/* Consistent spacing rhythm between sections. */
hr { margin: 1.1rem 0 !important; }
.stTabs { margin-top: 0.25rem; }
[data-testid="stVerticalBlock"] > div:has(> [data-testid="stMetric"]) {
    margin-bottom: 0.25rem;
}

/* Slightly bolder visual hierarchy: headers vs. body text. */
h1 { font-weight: 700 !important; letter-spacing: -0.01em; }
h2 { font-weight: 700 !important; }
h3, h4 { font-weight: 600 !important; }
[data-testid="stMetricValue"] { font-weight: 700 !important; }
[data-testid="stMetricLabel"] { font-weight: 500 !important; }
p, label, .stMarkdown, .stCaption { font-weight: 400; }

/* ── Mobile: ≤768px ──────────────────────────────────────────────────────── */
@media (max-width: 768px) {
    html, body { font-size: 16px !important; }

    /* Tighten the excess desktop padding without touching desktop rules. */
    .block-container {
        padding-left: 0.85rem !important;
        padding-right: 0.85rem !important;
        padding-top: 0.75rem !important;
    }
    [data-testid="stVerticalBlock"] { gap: 0.6rem !important; }
    hr { margin: 0.8rem 0 !important; }

    /* Bigger tap targets: buttons, form submits, and inline action links. */
    div[data-testid="stButton"] button,
    div[data-testid="stDownloadButton"] button,
    div[data-testid="stFormSubmitButton"] button,
    div[data-testid="stBaseButton-secondary"] button,
    div[data-testid="stBaseButton-primary"] button,
    .act-btn {
        min-height: 44px !important;
        padding: 10px 16px !important;
        font-size: 15px !important;
        border-radius: 8px !important;
    }
    .act-btn { display: inline-flex !important; align-items: center; justify-content: center; }

    /* Bigger tap targets: text/number/date inputs, selects, textareas. */
    div[data-baseweb="input"],
    div[data-baseweb="select"] > div:first-child,
    div[data-baseweb="datepicker"] input,
    div[data-baseweb="textarea"] {
        min-height: 44px !important;
    }
    div[data-baseweb="input"] input,
    div[data-baseweb="select"] > div:first-child {
        font-size: 16px !important;
    }
    [data-testid="stToggle"] { min-height: 44px; display: flex; align-items: center; }
    [data-testid="stCheckbox"] { min-height: 44px; display: flex; align-items: center; }

    /* Readability bump on narrow screens. */
    p, label, .stMarkdown, li { font-size: 15px !important; }
    [data-testid="stMetricValue"] { font-size: 1.5rem !important; }
    h1 { font-size: 1.5rem !important; }
    h2 { font-size: 1.2rem !important; }

    [data-testid="metric-container"], [data-testid="stMetric"] {
        padding: 10px 12px !important;
    }

    /* Keep the built-in sidebar collapse/expand control usable — the app
       hides Streamlit's default `header`, but the floating collapse
       control (shown when the sidebar is closed) must stay reachable. */
    [data-testid="collapsedControl"] {
        display: flex !important;
        visibility: visible !important;
        z-index: 999999 !important;
    }
    [data-testid="stSidebar"] { z-index: 999998 !important; }
}

/* ── Small mobile: ≤480px ────────────────────────────────────────────────── */
@media (max-width: 480px) {
    html, body { font-size: 17px !important; }
    .block-container {
        padding-left: 0.6rem !important;
        padding-right: 0.6rem !important;
    }
    [data-testid="metric-container"], [data-testid="stMetric"] {
        padding: 8px 10px !important;
    }
    h1 { font-size: 1.35rem !important; }
    .orders-table, .etbl, .erp-tbl { font-size: 12px !important; }
}
</style>
"""
