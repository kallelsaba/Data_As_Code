import dash

from dash import html, dcc, Input, Output

import plotly.express as px

from db import query


dash.register_page(
    __name__,
    path="/produits",
    name="Produits"
)


def get_data():
    sql = """
        SELECT
            product_category_name,
            price,
            freight_value
        FROM silver.stg_orders
        WHERE product_category_name IS NOT NULL
    """

    return query(sql)


def build_figures(df):

    by_category = (
        df.groupby("product_category_name", as_index=False)
        .agg(
            total_ca=("price", "sum"),
            nb_ventes=("price", "count")
        )
        .sort_values("total_ca", ascending=False)
        .head(10)
    )

    fig1 = px.bar(
        by_category.sort_values("total_ca"),
        x="total_ca",
        y="product_category_name",
        orientation="h",
        title="Top 10 catégories par CA",
        template="plotly_dark"
    )

    fig1.update_layout(
        yaxis_title="",
        xaxis_title="CA (R$)"
    )

    fig2 = px.bar(
        by_category.sort_values("nb_ventes"),
        x="nb_ventes",
        y="product_category_name",
        orientation="h",
        title="Top 10 catégories par nombre de ventes",
        template="plotly_dark",
        color_discrete_sequence=["#00cc96"]
    )

    fig2.update_layout(
        yaxis_title="",
        xaxis_title="Nombre de ventes"
    )

    return fig1, fig2


def layout():

    return html.Div([

        html.H2("📦 Produits & Catégories"),

        dcc.Graph(
            id="produits-ca"
        ),

        dcc.Graph(
            id="produits-ventes"
        ),

        dcc.Interval(
            id="produits-refresh",
            interval=5 * 60 * 1000,
            n_intervals=0
        )
    ])


@dash.callback(
    Output("produits-ca", "figure"),
    Output("produits-ventes", "figure"),
    Input("produits-refresh", "n_intervals")
)
def update_produits(n_intervals):

    df = get_data()

    fig1, fig2 = build_figures(df)

    return fig1, fig2
