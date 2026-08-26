
import dash

from dash import html, dcc, callback, Output, Input

import plotly.express as px

from db import query

dash.register_page(__name__, path="/ca", name="Chiffre d'affaires")

REFRESH_MS = 5 * 60 * 1000  # 5 minutes

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

layout = html.Div([

    html.H2("💰 Chiffre d'affaires"),

    html.Div(id="ca-kpis", className="mb-4"),

    dcc.Graph(id="ca-graph"),

    dcc.Interval(id="ca-interval", interval=REFRESH_MS, n_intervals=0),

])

@callback(

    Output("ca-kpis", "children"),

    Output("ca-graph", "figure"),

    Input("ca-interval", "n_intervals"),

)

def update_ca(n):

    df = get_data()

    monthly = df.groupby("month", as_index=False)["order_total_value"].sum()

    total_ca = df["order_total_value"].sum()

    nb_orders = df["order_id"].nunique()

    fig = px.line(

        monthly, x="month", y="order_total_value",

        title="Évolution du chiffre d'affaires mensuel",

        markers=True, template="plotly_dark"

    )

    fig.update_layout(yaxis_title="CA (R$)", xaxis_title="Mois")

    kpis = [

        html.Div(f"CA total: R$ {total_ca:,.0f}", className="badge bg-success fs-5 me-3"),

        html.Div(f"Commandes: {nb_orders:,}", className="badge bg-info fs-5"),

    ]

    return kpis, fig

