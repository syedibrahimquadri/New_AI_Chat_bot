"""Chat UI (Emerald Trust design): streamlit run src/ui/app.py"""

from __future__ import annotations

import base64
import html
import sys
import threading
import time
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

SUGGESTIONS = [
    ("🔍", "What is the lock-in for HDFC ELSS Tax Saver?"),
    ("％", "What is the exit load of HDFC Flexi Cap?"),
    ("🛡️", "Should I invest in HDFC Mid Cap right now?"),
]

TOPICS = [
    ("💸 Expense ratio", "What is the expense ratio of HDFC Large Cap Fund?"),
    ("🚪 Exit load", "What is the exit load of HDFC Mid Cap Fund?"),
    ("📅 Minimum SIP", "What is the minimum SIP of HDFC ELSS Tax Saver?"),
    ("🔒 ELSS lock-in", "What is the lock-in for HDFC ELSS Tax Saver?"),
    ("🌡️ Riskometer", "What is the riskometer rating of HDFC Small Cap Fund?"),
    ("📊 Benchmark", "What is the benchmark of HDFC Flexi Cap?"),
    ("🏆 Top holdings", "What are the top holdings of HDFC Large Cap Fund?"),
    ("👤 Fund manager", "Who is the fund manager of HDFC Mid Cap Fund?"),
    ("🏢 About HDFC Mutual Fund", "Who is the CEO of HDFC Mutual Fund?"),
]

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Plus+Jakarta+Sans:wght@600;700&display=swap');
:root { --surface:#faf8ff; --low:#f2f3ff; --mid:#eaedff; --ink:#131b2e; --muted:#3c4a43;
  --primary:#006c4f; --accent:#00b386; --mint:#59fdc5; --link:#005ac2; --err:#ba1a1a; --errbg:#ffdad6; }
.stApp, .stApp p, .stApp button, .stApp input, .stApp textarea { font-family:Inter, sans-serif; }
.stApp { background:var(--surface); color:var(--ink); }
[data-testid="stHeader"] { background:transparent; }
[data-testid="stSidebar"] { background:var(--low); }
.block-container { max-width:800px; padding-top:2rem; padding-bottom:7rem; }
.banner { background:linear-gradient(90deg,#e2e7ff,#d8f3f0); border-radius:1rem; padding:.85rem 1.1rem; margin:.8rem 0 1rem; font-size:.86rem; }
.banner b { font-weight:600; }
.hero { text-align:center; padding:1.5rem 0 1rem; animation:rise .3s ease-out; }
.hero h1 { font:700 2.1rem/1.2 'Plus Jakarta Sans',sans-serif; letter-spacing:-.02em; margin:0; padding:0; color:var(--ink); }
.hero p { color:var(--muted); margin:.4rem 0 0; font-size:.95rem; }
[data-testid="stChatMessage"] { background:#fff; border-radius:1rem; box-shadow:0 2px 10px #131b2e0a; animation:rise .22s ease-out; }
.label { font-weight:600; font-size:.82rem; margin-bottom:.15rem; }
.label.ok { color:var(--primary); } .label.no { color:var(--err); } .label.nf { color:#004395; }
.source { display:inline-block; max-width:100%; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; margin-top:.35rem; background:var(--low); border-radius:.6rem; padding:.3rem .7rem; font-size:.8rem; }
.source a { color:var(--link); text-decoration:none; }
.updated { color:var(--muted); font-size:.74rem; margin-top:.3rem; }
.stButton button { border-radius:14px; background:var(--low); border:0; color:var(--ink); font-size:.82rem; transition:background .15s ease, transform .15s ease; }
.stButton button:hover { background:var(--mid); color:var(--primary); transform:translateY(-1px); }
[data-testid="stChatInput"] { border-radius:1rem; box-shadow:0 8px 24px #006c4f1f; }
@keyframes rise { from { opacity:0; transform:translateY(6px);} to { opacity:1; transform:none;} }
@media (prefers-reduced-motion: reduce) { * { animation:none !important; transition:none !important; } }
@media (max-width:640px) { .hero h1 { font-size:1.6rem; } }
[data-testid="stToolbar"], [data-testid="stStatusWidget"], [data-testid="stDecoration"] { display:none !important; }
[data-testid="stBottom"], [data-testid="stBottom"] > div, [data-testid="stBottomBlockContainer"] { background:var(--surface) !important; }
[data-testid="stBottom"] div { background:transparent !important; }
[data-testid="stChatInput"] { background:#fff !important; }
[data-testid="stChatInput"] div, [data-testid="stChatInput"] textarea { background:#fff !important; }
.banner *, .label *, .source * { font-family:Inter, sans-serif; }
[data-testid="stExpander"] details { border:0; background:var(--low); border-radius:.7rem; }
.side-stats { display:flex; gap:.5rem; margin:.25rem 0 .5rem; }
.side-stats div { flex:1; background:#fff; border-radius:.8rem; padding:.55rem .6rem; font-size:.72rem; color:var(--muted); }
.side-stats b { display:block; font:700 1.35rem 'Plus Jakarta Sans',sans-serif; color:var(--primary); }
.side-title { font-size:.68rem; font-weight:600; letter-spacing:.06em; color:var(--muted); margin:.6rem 0 .1rem; }
.side-note { font-size:.78rem; line-height:1.7; color:var(--ink); }
[data-testid="stSidebar"] .stButton button { justify-content:flex-start; text-align:left; background:#fff; }
[data-testid="stSidebar"] .stButton { margin-bottom:-.7rem; }
[data-testid="stSidebar"] .stButton button { min-height:2rem; padding:.2rem .7rem; justify-content:flex-start; }
[data-testid="stSidebar"] .stButton button > div { justify-content:flex-start; }
[data-testid="stSidebarContent"] [data-testid="stSidebarHeader"] { height:2rem; padding:.25rem .75rem; }
[data-testid="stSidebar"] button p { font-size:.82rem; }
.brand { display:flex; align-items:center; gap:.6rem; margin:-1.6rem 0 .6rem; }
.brand img { width:42px; height:42px; }
.brand b { display:block; font:700 1.15rem/1.2 'Plus Jakarta Sans',sans-serif; color:var(--primary); }
.brand span { font-size:.72rem; color:var(--muted); }
</style>
"""


@st.cache_resource(show_spinner=False)
def warm_up() -> threading.Event:
    """Load models once, in the background, so the page paints immediately."""
    ready = threading.Event()

    def load() -> None:
        try:
            from src.ingest.embed import get_model
            from src.utils.config import load_settings

            get_model(load_settings())
        finally:
            ready.set()

    threading.Thread(target=load, daemon=True).start()
    return ready


def ask(question: str) -> dict:
    from src.generate.answer import answer_question
    from src.generate.guardrails import classify
    from src.llm.base import LLMError
    from src.retrieve.retriever import find_schemes
    from src.utils.config import load_settings

    settings = load_settings()
    named = find_schemes(question, settings)
    if named:
        st.session_state.last_scheme = named[0]
    elif st.session_state.get("last_scheme") and classify(question, []) == "needs_scheme":
        # Follow-up such as "what about its exit load?": reuse the fund in discussion.
        question = f"{question} for {st.session_state.last_scheme}"

    try:
        result = answer_question(question, settings)
    except (LLMError, RuntimeError) as exc:
        return {"kind": "error", "text": str(exc), "url": None, "date": None, "hits": []}
    return {
        "kind": result.type,
        "text": result.text,
        "url": result.citation_url,
        "date": result.last_updated_from_sources,
        "hits": result.hits,
    }


def render_label(kind: str) -> None:
    labels = {
        "answer": ("ok", "✓ Verified from source"),
        "refusal": ("no", "🛡 Facts-only policy"),
        "not_found": ("nf", "Not in sources"),
        "error": ("no", "Temporarily unavailable"),
    }
    css, text = labels.get(kind, labels["answer"])
    st.markdown(f'<div class="label {css}">{text}</div>', unsafe_allow_html=True)


def render_details(message: dict) -> None:
    if message.get("url"):
        url = html.escape(message["url"])
        st.markdown(
            f'<div class="source">🔗 <a href="{url}" target="_blank">{url}</a></div>',
            unsafe_allow_html=True,
        )
    if message.get("date"):
        st.markdown(
            f'<div class="updated">Last updated from sources: {html.escape(message["date"])}</div>',
            unsafe_allow_html=True,
        )


def typed(text: str):
    for word in text.split(" "):
        yield word + " "
        time.sleep(0.012)


def safe(text: str) -> str:
    return text.replace("$", "\\$")


st.set_page_config(page_title="MF Facts Assistant", page_icon=str(ROOT / "assets" / "logo.svg"), layout="centered")
st.markdown(CSS, unsafe_allow_html=True)
warm_up()

if "messages" not in st.session_state:
    st.session_state.messages = []

with st.sidebar:
    logo = base64.b64encode((ROOT / "assets" / "logo.svg").read_bytes()).decode()
    st.markdown(
        f'<div class="brand"><img src="data:image/svg+xml;base64,{logo}" alt="FundFacts logo">'
        "<div><b>FundFacts</b><span>Mutual fund assistant</span></div></div>",
        unsafe_allow_html=True,
    )
    if st.button("✨ New chat", use_container_width=True):
        st.session_state.messages = []
        st.session_state.last_scheme = None
        st.rerun()

    st.markdown(
        '<div class="side-stats"><div><b>15</b>HDFC funds</div><div><b>18</b>Public sources</div>'
        "</div>",
        unsafe_allow_html=True,
    )
    st.markdown('<div class="side-title">EXPLORE A TOPIC</div>', unsafe_allow_html=True)
    for index, (label, question) in enumerate(TOPICS):
        if st.button(label, key=f"topic{index}", use_container_width=True):
            st.session_state.pending = question
            st.rerun()
    st.markdown(
        '<div class="side-title">WHY TRUST IT</div>'
        '<div class="side-note">✓ Answers only from public sources<br>'
        "✓ A source link with every answer<br>"
        "✓ Shows when sources were last updated<br>"
        "✓ Never gives investment advice</div>",
        unsafe_allow_html=True,
    )

pending = st.session_state.pop("pending", None)

# One fixed slot: otherwise removing the welcome screen shifts every later element
# and Streamlit leaves faded copies of old messages on the page.
welcome = st.empty()
if not st.session_state.messages and not pending:
    panel = welcome.container()
    panel.markdown(
        '<div class="hero"><h1>Mutual Fund Facts Assistant</h1>'
        "<p>Ask anything factual about selected HDFC Mutual Fund schemes.</p></div>",
        unsafe_allow_html=True,
    )
    for icon, question in SUGGESTIONS:
        if panel.button(f"{icon} {question}", use_container_width=True):
            st.session_state.pending = question
            st.rerun()

st.markdown(
    '<div class="banner"><b>Facts-only. No investment advice.</b> Answers come from public '
    "mutual fund pages with a source link. It does not recommend buying, selling, or holding "
    "any scheme.</div>",
    unsafe_allow_html=True,
)

for message in st.session_state.messages:
    is_user = message["role"] == "user"
    with st.chat_message(message["role"], avatar="🧑" if is_user else "✅"):
        if not is_user:
            render_label(message["kind"])
        st.markdown(safe(message["text"]))
        if not is_user:
            render_details(message)

prompt = st.chat_input("Ask about a fund...") or pending
if prompt:
    welcome.empty()
    st.session_state.messages.append({"role": "user", "text": prompt})
    with st.chat_message("user", avatar="🧑"):
        st.markdown(safe(prompt))
    with st.chat_message("assistant", avatar="✅"):
        with st.spinner("Checking sources..."):
            reply = ask(prompt)
        render_label(reply["kind"])
        st.write_stream(typed(safe(reply["text"])))
        render_details(reply)
    st.session_state.messages.append({"role": "assistant", **reply})
