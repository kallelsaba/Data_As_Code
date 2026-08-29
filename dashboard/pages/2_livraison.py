import dash
from dash import html, dcc, callback, Output, Input
import dash_bootstrap_components as dbc
import plotly.express as px
from db import query
from components import kpi_card, chart_card

dash.register_page(__name__, path="/livraison", name="Livraison")


def get_data():
    sql = """
        SELECT DISTINCT
            order_id,
            order_purchase_timestamp,
            total_delivery_days,
            delivery_delay_days,
            is_delivered_on_time
        FROM silver.stg_orders
        WHERE total_delivery_days IS NOT NULL
    """
    df = query(sql)
    df["month"] = df["order_purchase_timestamp"].dt.to_period("M").astype(str)
    return df


layout = html.Div(
    [
        html.Div(id="livraison-content"),
        dcc.Interval(id="livraison-refresh", interval=5 * 60 * 1000, n_intervals=0),
    ]
)


@callback(
    Output("livraison-content", "children"),
    Input("livraison-refresh", "n_intervals"),
)
def update_dashboard(n_intervals):
    df = get_data()

    avg_delivery = df["total_delivery_days"].mean()
    pct_on_time = df["is_delivered_on_time"].mean() * 100

    kpis = dbc.Row(
        [
            kpi_card("bi-clock-history", "Délai moyen", f"{avg_delivery:.1f} jours", width=6),
            kpi_card("bi-check-circle", "Livré à l'heure", f"{pct_on_time:.1f}%", width=6),
        ]
    )

    monthly = df.groupby("month", as_index=False)["total_delivery_days"].mean()
    fig1 = px.line(monthly, x="month", y="total_delivery_days", markers=True)
    fig1.update_traces(line_color="#FF7A1A")
    fig1.update_layout(
        template="plotly_white", margin=dict(l=10, r=10, t=10, b=10),
        xaxis_title=None, yaxis_title="Jours", plot_bgcolor="white", paper_bgcolor="white",
    )

    fig2 = px.histogram(df, x="delivery_delay_days", nbins=40, color_discrete_sequence=["#FF7A1A"])
    fig2.update_layout(
        template="plotly_white", margin=dict(l=10, r=10, t=10, b=10),
        xaxis_title="Retard (jours, négatif = en avance)", yaxis_title="Nombre de commandes",
        plot_bgcolor="white", paper_bgcolor="white",
    )

    return html.Div(
        [
            kpis,
            chart_card("Délai moyen de livraison", "Évolution mensuelle (jours)",
                       dcc.Graph(figure=fig1, config={"displayModeBar": False})),
            chart_card("Écarts vs délai estimé", "Distribution des retards / avances",
                       dcc.Graph(figure=fig2, config={"displayModeBar": False})),
        ]
    )
