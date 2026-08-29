import dash

from dash import html, dcc, Input, Output

from db import query


dash.register_page(
    __name__,
    path="/",
    name="Accueil"
)


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


def kpi_card(title, value, color):

    return html.Div(
        [
            html.H4(
                title,
                className="text-muted"
            ),

            html.H2(
                value,
                className=f"text-{color}"
            ),
        ],
        className="border rounded p-3 text-center",
        style={"width": "23%"}
    )


def layout():

    return html.Div([

        html.H1("📊 Olist — Vue d'ensemble"),

        html.P(
            "Dashboard e-commerce basé sur le pipeline "
            "dataops (bronze → silver → analytics).",
            className="text-muted"
        ),

        html.Div(
            id="home-kpis",
            className="d-flex justify-content-between mt-4"
        ),

        html.Hr(
            className="mt-4"
        ),

        html.P(
            "Utilise le menu à gauche pour explorer : "
            "CA, Livraison, Satisfaction, Produits."
        ),

        dcc.Interval(
            id="home-refresh",
            interval=5 * 60 * 1000,
            n_intervals=0
        )
    ])


@dash.callback(
    Output("home-kpis", "children"),
    Input("home-refresh", "n_intervals")
)
def update_home(n_intervals):

    k = get_kpis()

    return [

        kpi_card(
            "CA total",
            f"R$ {k['ca_total']:,.0f}",
            "success"
        ),

        kpi_card(
            "Commandes",
            f"{k['nb_commandes']:,}",
            "info"
        ),

        kpi_card(
            "Note moyenne",
            f"{k['note_moyenne']:.2f}/5",
            "warning"
        ),

        kpi_card(
            "Livré à l'heure",
            f"{k['pct_a_lheure']:.1f}%",
            "primary"
        ),
    ]
