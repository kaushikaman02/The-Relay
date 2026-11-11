
import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import time
from pathlib import Path
from datetime import datetime

# ==================================================
# THE RELAY V2 - CONFIGURATION
# ==================================================

BASE_DIR = Path(__file__).resolve().parent

SIMULATOR_URL = "http://127.0.0.1:8000"
RELAY_URL = "http://127.0.0.1:8001"

RPM_LIMIT = 30
RPD_LIMIT = 1000
TPM_LIMIT = 8000
TPD_LIMIT = 200000

REFRESH_SECONDS = 5

HISTORY_FILE = BASE_DIR / "dashboard_metrics_history.csv"

LOAD_TEST_FILES = [
    BASE_DIR / "relay_retry_load_results.csv",
    BASE_DIR / "results" / "relay_retry_load_results.csv"
]

st.set_page_config(
    page_title="THE RELAY | V2 Monitoring",
    page_icon="⚡",
    layout="wide"
)

# ==================================================
# CUSTOM STYLING
# ==================================================

st.markdown("""
<style>
.stApp {
    background-color: #0e1117;
}

[data-testid="stMetric"] {
    background: #1b2230;
    padding: 16px;
    border-radius: 10px;
    border: 1px solid #303849;
}

[data-testid="stMetricValue"] {
    color: #ffffff;
}

section[data-testid="stSidebar"] {
    background-color: #151b25;
}

h1, h2, h3 {
    color: #f5f5f5;
}

</style>
""", unsafe_allow_html=True)


# ==================================================
# API FUNCTIONS
# ==================================================

def fetch_endpoint(base_url, endpoint):

    try:
        response = requests.get(
            f"{base_url}{endpoint}",
            timeout=3
        )

        response.raise_for_status()

        return response.json(), True

    except (requests.RequestException, ValueError):
        return {}, False


def fetch_metrics(url):
    return fetch_endpoint(url, "/metrics")


def fetch_health(url):
    return fetch_endpoint(url, "/health")


# ==================================================
# HISTORICAL METRICS STORAGE
# ==================================================

def save_snapshot(sim, relay):

    now = time.time()

    previous = st.session_state.get(
        "last_snapshot_time", 0
    )

    if now - previous < 4:
        return

    st.session_state.last_snapshot_time = now

    row = {
        "timestamp": datetime.now().isoformat(
            timespec="seconds"
        ),

        "daily_requests": sim.get("daily_requests", 0),
        "daily_tokens": sim.get("daily_tokens", 0),
        "requests_last_minute": sim.get(
            "requests_last_minute", 0
        ),

        "in_flight": sim.get("in_flight", 0),

        "queue_size": relay.get("queue_size", 0),
        "completed": relay.get("completed", 0),
        "rejected": relay.get("rejected", 0),
        "failed": relay.get("failed", 0),

        "average_wait_ms": relay.get(
            "average_wait_ms", 0
        ),

        "average_processing_ms": relay.get(
            "average_processing_ms", 0
        )
    }

    new_data = pd.DataFrame([row])

    try:

        if HISTORY_FILE.exists():

            new_data.to_csv(
                HISTORY_FILE,
                mode="a",
                header=False,
                index=False
            )

        else:

            new_data.to_csv(
                HISTORY_FILE,
                index=False
            )

    except (OSError, PermissionError) as error:
        st.warning(f"Could not save history: {error}")


# ==================================================
# LOAD TEST ANALYTICS
# ==================================================

def load_test_results():

    for file_path in LOAD_TEST_FILES:

        if file_path.exists():

            try:

                df = pd.read_csv(file_path)

                required = {
                    "status_code",
                    "latency_ms"
                }

                if required.issubset(df.columns):

                    df["status_code"] = pd.to_numeric(
                        df["status_code"],
                        errors="coerce"
                    )

                    df["latency_ms"] = pd.to_numeric(
                        df["latency_ms"],
                        errors="coerce"
                    )

                    if "retries" not in df.columns:
                        df["retries"] = 0

                    df["retries"] = pd.to_numeric(
                        df["retries"],
                        errors="coerce"
                    ).fillna(0)

                    return df.dropna(
                        subset=["status_code", "latency_ms"]
                    )

            except (OSError, ValueError, pd.errors.ParserError):
                pass

    return pd.DataFrame()


# ==================================================
# HEADER
# ==================================================

def render_dashboard():

    st.title("⚡ THE RELAY")

    st.subheader(
        "API Reliability & Monitoring Dashboard — V2"
    )

    st.caption(
        "Advanced monitoring of API traffic, rate limits, "
        "latency, queue performance and service reliability."
    )

    col1, col2 = st.columns([3, 1])

    with col1:

        st.write(
            "Last updated:",
            datetime.now().strftime(
                "%d %b %Y | %H:%M:%S"
            )
        )

        st.caption(
            f"Automatic refresh: Every {REFRESH_SECONDS} seconds"
        )

    with col2:

        if st.button(
            "🔄 Refresh Metrics",
            use_container_width=True
        ):
            st.rerun()

    st.divider()

    # ==================================================
    # FETCH SERVICES
    # ==================================================

    sim_metrics, sim_online = fetch_metrics(
        SIMULATOR_URL
    )

    relay_metrics, relay_online = fetch_metrics(
        RELAY_URL
    )

    sim_health, sim_health_online = fetch_health(
        SIMULATOR_URL
    )

    relay_health, relay_health_online = fetch_health(
        RELAY_URL
    )

    # ==================================================
    # 1. SERVICE HEALTH
    # ==================================================

    st.header("1. Service Health")

    c1, c2 = st.columns(2)

    with c1:

        if sim_online and sim_health_online:
            st.success("🟢 Simulator: ONLINE")
        else:
            st.error("🔴 Simulator: OFFLINE")

    with c2:

        if relay_online and relay_health_online:
            st.success("🟢 Relay API: ONLINE")
        else:
            st.error("🔴 Relay API: OFFLINE")

    if not sim_online and not relay_online:
        st.warning(
            "Start the simulator and relay servers "
            "before using the monitoring dashboard."
        )

    # ==================================================
    # SAVE HISTORICAL SNAPSHOT
    # ==================================================

    if sim_online or relay_online:

        save_snapshot(
            sim_metrics if sim_online else {},
            relay_metrics if relay_online else {}
        )

    # ==================================================
    # 2. API USAGE AND RATE LIMITS
    # ==================================================

    st.divider()

    st.header("2. API Usage & Rate Limits")

    if sim_online:

        daily_requests = sim_metrics.get(
            "daily_requests", 0
        )

        daily_tokens = sim_metrics.get(
            "daily_tokens", 0
        )

        requests_minute = sim_metrics.get(
            "requests_last_minute", 0
        )

        in_flight = sim_metrics.get(
            "in_flight", 0
        )

        rpm_remaining = sim_metrics.get(
            "rate_limits_remaining",
            max(0, RPM_LIMIT - requests_minute)
        )

        c1, c2, c3, c4 = st.columns(4)

        c1.metric(
            "Daily Requests",
            f"{daily_requests:,}"
        )

        c2.metric(
            "Daily Tokens",
            f"{daily_tokens:,}"
        )

        c3.metric(
            "Requests / Minute",
            requests_minute
        )

        c4.metric(
            "In-flight Requests",
            in_flight
        )

        c1, c2, c3 = st.columns(3)

        c1.metric(
            "RPM Remaining",
            rpm_remaining,
            delta=f"Limit: {RPM_LIMIT}"
        )

        c2.metric(
            "Daily Requests Remaining",
            max(0, RPD_LIMIT - daily_requests)
        )

        c3.metric(
            "Daily Tokens Remaining",
            f"{max(0, TPD_LIMIT - daily_tokens):,}"
        )

        # RPM chart

        rpm_data = pd.DataFrame({
            "Category": ["Used", "Remaining"],
            "Requests": [
                requests_minute,
                max(0, RPM_LIMIT - requests_minute)
            ]
        })

        fig = px.bar(
            rpm_data,
            x="Category",
            y="Requests",
            color="Category",
            text="Requests",
            title="Requests Per Minute Usage"
        )

        st.plotly_chart(
            fig,
            use_container_width=True
        )

        # Token budget chart

        token_data = pd.DataFrame({
            "Category": ["Used", "Remaining"],
            "Tokens": [
                daily_tokens,
                max(0, TPD_LIMIT - daily_tokens)
            ]
        })

        fig = px.bar(
            token_data,
            x="Category",
            y="Tokens",
            color="Category",
            text="Tokens",
            title="Daily Token Budget Usage"
        )

        st.plotly_chart(
            fig,
            use_container_width=True
        )

    else:

        st.warning("Simulator metrics unavailable.")

    # ==================================================
    # 3. QUEUE AND WORKER PERFORMANCE
    # ==================================================

    st.divider()

    st.header("3. Queue & Worker Performance")

    if relay_online:

        workers = relay_metrics.get("workers", 0)

        queue_capacity = relay_metrics.get(
            "queue_capacity", 0
        )

        queue_size = relay_metrics.get(
            "queue_size", 0
        )

        completed = relay_metrics.get(
            "completed", 0
        )

        rejected = relay_metrics.get(
            "rejected", 0
        )

        failed = relay_metrics.get(
            "failed", 0
        )

        avg_wait = relay_metrics.get(
            "average_wait_ms", 0
        )

        avg_processing = relay_metrics.get(
            "average_processing_ms", 0
        )

        c1, c2, c3, c4 = st.columns(4)

        c1.metric("Workers", workers)
        c2.metric("Queue Capacity", queue_capacity)
        c3.metric("Queue Size", queue_size)
        c4.metric("Completed Requests", completed)

        c1, c2, c3 = st.columns(3)

        c1.metric("Rejected Requests", rejected)
        c2.metric("Failed Requests", failed)

        c3.metric(
            "Average Queue Wait",
            f"{avg_wait:.2f} ms"
        )

        st.metric(
            "Average Processing Time",
            f"{avg_processing:.2f} ms"
        )

        # Queue utilization

        utilization = (
            queue_size / queue_capacity * 100
            if queue_capacity > 0 else 0
        )

        st.write(
            f"Queue Utilization: {utilization:.1f}%"
        )

        st.progress(
            min(1.0, max(0.0, utilization / 100))
        )

        # Completion share

        total_handled = completed + rejected + failed

        completion_share = (
            completed / total_handled * 100
            if total_handled > 0 else 0
        )

        st.metric(
            "Completion Share",
            f"{completion_share:.2f}%"
        )

        st.caption(
            "Completion share is completed requests divided "
            "by completed + rejected + failed requests. "
            "Rejected requests are not necessarily server failures."
        )

        queue_data = pd.DataFrame({
            "Status": [
                "Completed",
                "Rejected",
                "Failed"
            ],

            "Requests": [
                completed,
                rejected,
                failed
            ]
        })

        fig = px.pie(
            queue_data,
            names="Status",
            values="Requests",
            title="Request Processing Distribution",
            hole=0.5
        )

        st.plotly_chart(
            fig,
            use_container_width=True
        )

    else:

        st.warning("Relay metrics unavailable.")

    # ==================================================
    # 4. LATENCY ANALYTICS
    # ==================================================

    st.divider()

    st.header("4. Latency Analytics")

    load_df = load_test_results()

    if not load_df.empty:

        latencies = load_df["latency_ms"]

        successful = load_df[
            (load_df["status_code"] >= 200) &
            (load_df["status_code"] < 300)
        ]

        success_latencies = successful["latency_ms"]

        c1, c2, c3, c4 = st.columns(4)

        c1.metric(
            "P50 Latency",
            f"{latencies.quantile(0.50):.2f} ms"
        )

        c2.metric(
            "P95 Latency",
            f"{latencies.quantile(0.95):.2f} ms"
        )

        c3.metric(
            "P99 Latency",
            f"{latencies.quantile(0.99):.2f} ms"
        )

        c4.metric(
            "Average Latency",
            f"{latencies.mean():.2f} ms"
        )

        st.caption(
            "Percentiles are calculated from the available "
            "load-test CSV, not from live requests."
        )

        if not success_latencies.empty:

            st.metric(
                "Average Successful Request Latency",
                f"{success_latencies.mean():.2f} ms"
            )

        # Latency distribution

        fig = px.histogram(
            load_df,
            x="latency_ms",
            nbins=20,
            title="Request Latency Distribution"
        )

        st.plotly_chart(
            fig,
            use_container_width=True
        )

    else:

        st.info(
            "No load-test results found. Run "
            "src/test_relay_load.py to generate "
            "relay_retry_load_results.csv."
        )

    # ==================================================
    # 5. HTTP ERROR ANALYTICS
    # ==================================================

    st.divider()

    st.header("5. HTTP Error Analytics")

    if not load_df.empty:

        status_data = (
            load_df["status_code"]
            .value_counts()
            .sort_index()
            .reset_index()
        )

        status_data.columns = [
            "HTTP Status",
            "Requests"
        ]

        status_data["HTTP Status"] = (
            status_data["HTTP Status"]
            .astype(int)
            .astype(str)
        )

        fig = px.bar(
            status_data,
            x="HTTP Status",
            y="Requests",
            color="HTTP Status",
            text="Requests",
            title="HTTP Response Status Distribution"
        )

        st.plotly_chart(
            fig,
            use_container_width=True
        )

        c1, c2, c3, c4 = st.columns(4)

        total = len(load_df)

        count_200 = len(
            load_df[load_df["status_code"] == 200]
        )

        count_429 = len(
            load_df[load_df["status_code"] == 429]
        )

        count_503 = len(
            load_df[load_df["status_code"] == 503]
        )

        count_504 = len(
            load_df[load_df["status_code"] == 504]
        )

        c1.metric("HTTP 200", count_200)
        c2.metric("HTTP 429", count_429)
        c3.metric("HTTP 503", count_503)
        c4.metric("HTTP 504", count_504)

        success_rate = count_200 / total * 100

        st.metric(
            "HTTP 200 Success Rate",
            f"{success_rate:.2f}%"
        )

        st.caption(
            "HTTP status analytics use the latest available "
            "load-test CSV. Other status codes are shown in "
            "the distribution chart."
        )

        st.metric(
            "Total Retry Attempts",
            int(load_df["retries"].sum())
        )

    else:

        st.info(
            "HTTP analytics will appear after a load test."
        )

    # ==================================================
    # 6. HISTORICAL PERFORMANCE
    # ==================================================

    st.divider()

    st.header("6. Historical Performance")

    if HISTORY_FILE.exists():

        try:

            history = pd.read_csv(HISTORY_FILE)

            if not history.empty:

                history["timestamp"] = pd.to_datetime(
                    history["timestamp"],
                    errors="coerce"
                )

                history = history.dropna(
                    subset=["timestamp"]
                )

                st.caption(
                    f"Recorded snapshots: {len(history)}"
                )

                history_metric = st.selectbox(
                    "Select historical metric",
                    [
                        "daily_requests",
                        "daily_tokens",
                        "queue_size",
                        "completed",
                        "rejected",
                        "failed",
                        "average_wait_ms",
                        "average_processing_ms"
                    ]
                )

                fig = px.line(
                    history,
                    x="timestamp",
                    y=history_metric,
                    markers=True,
                    title=f"Historical {history_metric}"
                )

                st.plotly_chart(
                    fig,
                    use_container_width=True
                )

                with st.expander(
                    "View historical metrics data"
                ):

                    st.dataframe(
                        history.tail(100),
                        use_container_width=True
                    )

                csv_data = history.to_csv(
                    index=False
                ).encode("utf-8")

                st.download_button(
                    "Download Historical Metrics CSV",
                    data=csv_data,
                    file_name="dashboard_metrics_history.csv",
                    mime="text/csv"
                )

        except (OSError, ValueError, KeyError) as error:

            st.warning(
                f"Could not load historical data: {error}"
            )

    else:

        st.info(
            "Historical data will appear automatically "
            "as the dashboard collects snapshots."
        )

    # ==================================================
    # FOOTER
    # ==================================================

    st.divider()

    st.caption(
        "⚡ THE RELAY V2 | API Reliability Engineering Project"
    )

    st.caption(
        "Live metrics: Local simulator and relay services. "
        "Historical and latency analytics: Local CSV files."
    )


# ==================================================
# AUTOMATIC REFRESH
# ==================================================

@st.fragment(run_every=REFRESH_SECONDS)
def live_dashboard():
    render_dashboard()


live_dashboard()
