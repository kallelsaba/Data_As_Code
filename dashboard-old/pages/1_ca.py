import dash
from dash import html, dcc, callback, Output, Input
import dash_bootstrap_components as dbc
import plotly.express as px
from db import query
from components import kpi_card, chart_card

dash.register_page(__name__, path="/ca", name="Chiffre d'affaires")

REFRESH_MS = 5 * 60 * 1000


def get_data():
    sql = """
        SELECT DISTINCT
            order_id, order_purchase_timestamp, order_total_value
        FROM silver.stg_orders
        WHERE order_purchase_timestamp IS NOT NULL
    """
    df = query(sql)
    df["month"] = df["order_purchase_timestamp"].dt.to_period("M").astype(str)
    return df


layout = html.Div(
    [
        html.Div(id="ca-content"),
        dcc.Interval(id="ca-interval", interval=REFRESH_MS, n_intervals=0),
    ]
)


@callback(
    Output("ca-content", "children"),
    Input("ca-interval", "n_intervals"),
)
def update_ca(n):
    df = get_data()
    monthly = df.groupby("month", as_index=False)["order_total_value"].sum()

    total_ca = df["order_total_value"].sum()
    nb_orders = df["order_id"].nunique()
    avg_order = total_ca / nb_orders if nb_orders else 0

    fig = px.line(monthly, x="month", y="order_total_value", markers=True)
    fig.update_traces(line_color="#FF7A1A", fill="tozeroy", fillcolor="rgba(255,122,26,0.10)")
    fig.update_layout(
        template="plotly_white",
        margin=dict(l=10, r=10, t=10, b=10),
        xaxis_title=None,
        yaxis_title="CA (R$)",
        plot_bgcolor="white",
        paper_bgcolor="white",
    )

    kpis = dbc.Row(
        [
            kpi_card("bi-cash-stack", "CA total", f"R$ {total_ca:,.0f}", width=4),
            kpi_card("bi-bag-check", "Commandes", f"{nb_orders:,}", width=4),
            kpi_card("bi-graph-up-arrow", "Panier moyen", f"R$ {avg_order:,.2f}", width=4),
        ]
    )

    chart = chart_card(
        "Évolution du chiffre d'affaires",
        "CA mensuel total (R$)",
        dcc.Graph(figure=fig, config={"displayModeBar": False}),
    )

    return html.Div([kpis, chart])
