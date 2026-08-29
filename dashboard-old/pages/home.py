import dash
from dash import html, dcc, Input, Output
import dash_bootstrap_components as dbc
from db import query
from components import kpi_card

dash.register_page(__name__, path="/", name="Accueil")


def get_kpis():
    sql = """
        SELECT DISTINCT
            order_id,
            order_total_value,
            review_score,
            is_delivered_on_time,
            total_delivery_days
        FROM silver.stg_orders
    """
    df = query(sql)
    return {
        "ca_total": df["order_total_value"].sum(),
        "nb_commandes": df["order_id"].nunique(),
        "note_moyenne": df["review_score"].mean(),
        "pct_a_lheure": df["is_delivered_on_time"].mean() * 100,
    }


layout = html.Div(
    [
        html.P(
            "De la donnée brute aux insights : Suivez en temps réel la transformation des données e-commerce, de leur collecte à l’analyse décisionnelle.",
            className="text-muted mb-4",
        ),
        html.Div(id="home-kpis"),
        dcc.Interval(id="home-refresh", interval=5 * 60 * 1000, n_intervals=0),
    ]
)


@dash.callback(
    Output("home-kpis", "children"),
    Input("home-refresh", "n_intervals"),
)
def update_home(n_intervals):
    k = get_kpis()
    return dbc.Row(
        [
            kpi_card("bi-cash-stack", "CA total", f"R$ {k['ca_total']:,.0f}"),
            kpi_card("bi-bag-check", "Commandes", f"{k['nb_commandes']:,}"),
            kpi_card("bi-star-fill", "Note moyenne", f"{k['note_moyenne']:.2f}/5"),
            kpi_card("bi-truck", "Livré à l'heure", f"{k['pct_a_lheure']:.1f}%"),
        ]
    )
