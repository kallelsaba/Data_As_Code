import dash

from dash import html, dcc, callback, Output, Input

import plotly.express as px

from db import query


dash.register_page(
    __name__,
    path="/livraison",
    name="Livraison"
)


# ==================================================
# Récupération des données
# ==================================================

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

    df["month"] = (
        df["order_purchase_timestamp"]
        .dt.to_period("M")
        .astype(str)
    )

    return df


# ==================================================
# Layout
# ==================================================

def layout():

    return html.Div([

        html.H2("🚚 Performance logistique"),

        # Rafraîchissement toutes les 5 minutes
        dcc.Interval(
            id="livraison-refresh",
            interval=5 * 60 * 1000,  # 5 minutes
            n_intervals=0
        ),

        # KPI
        html.Div(
            id="livraison-kpis",
            className="mb-4"
        ),

        # Graphique délai moyen
        dcc.Graph(
            id="livraison-monthly-chart"
        ),

        # Graphique retard
        dcc.Graph(
            id="livraison-delay-chart"
        )

    ])


# ==================================================
# Callback : actualisation des données
# ==================================================

@callback(
    Output("livraison-kpis", "children"),
    Output("livraison-monthly-chart", "figure"),
    Output("livraison-delay-chart", "figure"),
    Input("livraison-refresh", "n_intervals")
)
def update_dashboard(n_intervals):

    # Recharger les données depuis PostgreSQL
    df = get_data()

    # ==================================================
    # KPI
    # ==================================================

    avg_delivery = df["total_delivery_days"].mean()

    pct_on_time = (
        df["is_delivered_on_time"].mean() * 100
    )

    kpis = html.Div([

        html.Div(
            f"Délai moyen : {avg_delivery:.1f} jours",
            className="badge bg-primary fs-5 me-3"
        ),

        html.Div(
            f"Livré à l'heure : {pct_on_time:.1f}%",
            className="badge bg-success fs-5"
        )

    ])


    # ==================================================
    # Délai moyen par mois
    # ==================================================

    monthly = (
        df.groupby(
            "month",
            as_index=False
        )["total_delivery_days"]
        .mean()
    )

    fig1 = px.line(
        monthly,
        x="month",
        y="total_delivery_days",
        title="Délai moyen de livraison par mois (jours)",
        markers=True,
        template="plotly_dark"
    )

    fig1.update_layout(
        xaxis_title="Mois",
        yaxis_title="Jours"
    )


    # ==================================================
    # Distribution des retards
    # ==================================================

    fig2 = px.histogram(
        df,
        x="delivery_delay_days",
        title="Distribution des écarts vs délai estimé (jours)",
        template="plotly_dark",
        nbins=40
    )

    fig2.update_layout(
        xaxis_title="Retard (jours, négatif = en avance)",
        yaxis_title="Nombre de commandes"
    )


    return kpis, fig1, fig2
