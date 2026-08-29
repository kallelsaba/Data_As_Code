import dash
from dash import html, dcc, Input, Output, callback
import plotly.express as px
from db import query
from components import chart_card

dash.register_page(__name__, path="/produits", name="Produits")


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
        .agg(total_ca=("price", "sum"), nb_ventes=("price", "count"))
        .sort_values("total_ca", ascending=False)
        .head(10)
    )

    fig1 = px.bar(
        by_category.sort_values("total_ca"), x="total_ca", y="product_category_name",
        orientation="h", color_discrete_sequence=["#FF7A1A"],
    )
    fig1.update_layout(
        template="plotly_white", margin=dict(l=10, r=10, t=10, b=10),
        yaxis_title=None, xaxis_title="CA (R$)", plot_bgcolor="white", paper_bgcolor="white",
    )

    fig2 = px.bar(
        by_category.sort_values("nb_ventes"), x="nb_ventes", y="product_category_name",
        orientation="h", color_discrete_sequence=["#1F2937"],
    )
    fig2.update_layout(
        template="plotly_white", margin=dict(l=10, r=10, t=10, b=10),
        yaxis_title=None, xaxis_title="Nombre de ventes", plot_bgcolor="white", paper_bgcolor="white",
    )

    return fig1, fig2


layout = html.Div(
    [
        html.Div(id="produits-content"),
        dcc.Interval(id="produits-refresh", interval=5 * 60 * 1000, n_intervals=0),
    ]
)


@callback(
    Output("produits-content", "children"),
    Input("produits-refresh", "n_intervals"),
)
def update_produits(n_intervals):
    df = get_data()
    fig1, fig2 = build_figures(df)

    return html.Div(
        [
            chart_card("Top 10 catégories par CA", "Chiffre d'affaires par catégorie de produit",
                       dcc.Graph(figure=fig1, config={"displayModeBar": False})),
            chart_card("Top 10 catégories par ventes", "Nombre de ventes par catégorie de produit",
                       dcc.Graph(figure=fig2, config={"displayModeBar": False})),
        ]
    )
