import dash
from dash import html, dcc, Input, Output
import dash_bootstrap_components as dbc
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from db import query
from components import kpi_card, chart_card

dash.register_page(__name__, path="/", name="Accueil")

ORANGE_SCALE = ["#FF7A1A", "#FF9A47", "#FFB877", "#FFD9B3", "#FFE9D2"]


def get_kpis():
    sql = """
        SELECT DISTINCT
            order_id, order_total_value, review_score,
            is_delivered_on_time, total_delivery_days
        FROM silver.stg_orders
    """
    df = query(sql)
    return {
        "ca_total": df["order_total_value"].sum(),
        "nb_commandes": df["order_id"].nunique(),
        "note_moyenne": df["review_score"].mean(),
        "pct_a_lheure": df["is_delivered_on_time"].mean() * 100,
    }


def get_revenue_trend():
    sql = """
        SELECT DISTINCT order_id, order_purchase_timestamp, order_total_value
        FROM silver.stg_orders
        WHERE order_purchase_timestamp IS NOT NULL
    """
    df = query(sql)
    df["month"] = df["order_purchase_timestamp"].dt.to_period("M").astype(str)
    return df.groupby("month", as_index=False)["order_total_value"].sum()


def get_top_categories():
    sql = """
        SELECT product_category_name, price
        FROM silver.stg_orders
        WHERE product_category_name IS NOT NULL
    """
    df = query(sql)
    by_cat = (
        df.groupby("product_category_name", as_index=False)["price"]
        .sum().sort_values("price", ascending=False)
    )
    top5 = by_cat.head(5).copy()
    autres = by_cat["price"].iloc[5:].sum()
    if autres > 0:
        top5 = pd.concat(
            [top5, pd.DataFrame([{"product_category_name": "Autres", "price": autres}])],
            ignore_index=True,
        )
    return top5


def get_review_distribution():
    sql = """
        SELECT review_score
        FROM silver.stg_orders
        WHERE review_score IS NOT NULL
    """
    df = query(sql)
    counts = df["review_score"].value_counts().sort_index().reset_index()
    counts.columns = ["review_score", "count"]
    return counts


def get_delivery_split():
    sql = """
        SELECT DISTINCT order_id, is_delivered_on_time
        FROM silver.stg_orders
        WHERE is_delivered_on_time IS NOT NULL
    """
    df = query(sql)
    on_time = df["is_delivered_on_time"].mean() * 100
    return on_time, 100 - on_time


layout = html.Div(
    [
        html.P(
            "De la donnée brute aux insights : Suivez en temps réel la transformation des données e-commerce, de leur collecte à l’analyse décisionnelle.",
            className="text-muted mb-4",
        ),
        html.Div(id="home-kpis"),
        html.Div(id="home-charts"),
        dcc.Interval(id="home-refresh", interval=5 * 60 * 1000, n_intervals=0),
    ]
)


@dash.callback(
    Output("home-kpis", "children"),
    Output("home-charts", "children"),
    Input("home-refresh", "n_intervals"),
)
def update_home(n_intervals):
    k = get_kpis()

    kpis = dbc.Row(
        [
            kpi_card("bi-cash-stack", "CA total", f"R$ {k['ca_total']:,.0f}", variant="orange"),
            kpi_card("bi-bag-check", "Commandes", f"{k['nb_commandes']:,}", variant="orange"),
            kpi_card("bi-star-fill", "Note moyenne", f"{k['note_moyenne']:.2f}/5", variant="orange"),
            kpi_card("bi-truck", "Livré à l'heure", f"{k['pct_a_lheure']:.1f}%", variant="orange"),
        ]
    )

    # --- Revenue Analytics ---
    revenue = get_revenue_trend()
    fig_revenue = px.area(revenue, x="month", y="order_total_value")
    fig_revenue.update_traces(line_color="#FF7A1A", fillcolor="rgba(255,122,26,0.12)")
    fig_revenue.update_layout(
        template="plotly_white", margin=dict(l=10, r=10, t=10, b=10),
        xaxis_title=None, yaxis_title="CA (R$)", plot_bgcolor="white", paper_bgcolor="white",
    )

    # --- Monthly Target (gauge) ---
    pct_a_lheure = k["pct_a_lheure"]
    pct_en_retard = 100 - pct_a_lheure
    nb_commandes = k["nb_commandes"]
    nb_a_lheure = int(nb_commandes * pct_a_lheure / 100)
    nb_en_retard = nb_commandes - nb_a_lheure
    fig_gauge = go.Figure(go.Indicator(
        mode="gauge+number",
        value=pct_a_lheure,
        number={"suffix": "%", "font": {"size": 30, "color": "#1F2937"}},
        gauge={
            "axis": {"range": [0, 100], "visible": False},
            "bar": {"color": "#FF7A1A", "thickness": 0.3},
            "bgcolor": "#FFF1E6",
            "borderwidth": 0,
        },
    ))
    fig_gauge.update_layout(margin=dict(l=10, r=10, t=30, b=10), height=210, paper_bgcolor="white")

    gauge_legend = html.Div([
        html.Div([
            html.Span(className="legend-dot", style={"background": "#FF7A1A"}),
            html.Span("À l'heure", className="legend-label"),
            html.Span(f"{pct_a_lheure:.1f}%", className="legend-value"),
        ], className="legend-row"),
        html.Div([
            html.Span(className="legend-dot", style={"background": "#FFD9B3"}),
            html.Span("En retard", className="legend-label"),
            html.Span(f"{pct_en_retard:.1f}%", className="legend-value"),
        ], className="legend-row"),
        html.Div([
            html.Span(className="legend-dot", style={"background": "#FFF1E6"}),
            html.Span("Commandes livrées", className="legend-label"),
            html.Span(f"{nb_a_lheure:,}", className="legend-value"),
        ], className="legend-row"),
        html.Div([
            html.Span(className="legend-dot", style={"background": "#F0EEEB"}),
            html.Span("Commandes en retard", className="legend-label"),
            html.Span(f"{nb_en_retard:,}", className="legend-value"),
        ], className="legend-row"),
    ])

    # --- Top Categories (donut + legend) ---
    top_cats = get_top_categories()
    fig_donut = px.pie(
        top_cats, names="product_category_name", values="price",
        hole=0.62, color_discrete_sequence=ORANGE_SCALE,
    )
    fig_donut.update_traces(textinfo="none")
    fig_donut.update_layout(margin=dict(l=10, r=10, t=10, b=10), showlegend=False,
                             height=200, paper_bgcolor="white")
    cat_legend = html.Div(
        [
            html.Div(
                [
                    html.Span(className="legend-dot",
                              style={"background": ORANGE_SCALE[i % len(ORANGE_SCALE)]}),
                    html.Span(row["product_category_name"], className="legend-label"),
                    html.Span(f"R$ {row['price']:,.0f}", className="legend-value"),
                ],
                className="legend-row",
            )
            for i, row in top_cats.iterrows()
        ]
    )

    # --- Répartition des notes ---
    reviews = get_review_distribution()
    total_reviews = reviews["count"].sum()
    fig_reviews = px.bar(reviews, x="review_score", y="count", color_discrete_sequence=["#FF7A1A"])
    fig_reviews.update_layout(
        template="plotly_white", margin=dict(l=10, r=10, t=10, b=10),
        xaxis_title="Note", yaxis_title="Nb avis", plot_bgcolor="white", paper_bgcolor="white",
        height=200,
    )

    reviews_legend = html.Div([
        html.Div([
            html.Span(className="legend-dot",
                      style={"background": ORANGE_SCALE[i % len(ORANGE_SCALE)]}),
            html.Span(f"★ {int(row['review_score'])}", className="legend-label"),
            html.Span(f"{row['count']:,} ({row['count']/total_reviews*100:.1f}%)",
                      className="legend-value"),
        ], className="legend-row")
        for i, row in reviews.iterrows()
    ])


    # --- Livraison à l'heure vs en retard ---
    on_time, late = get_delivery_split()
    fig_delivery = go.Figure(go.Bar(
        x=[on_time, late], y=["À l'heure", "En retard"], orientation="h",
        marker_color=["#FF7A1A", "#FFD9B3"],
        text=[f"{on_time:.0f}%", f"{late:.0f}%"], textposition="outside",
    ))
    fig_delivery.update_layout(
        template="plotly_white", margin=dict(l=10, r=40, t=10, b=10),
        xaxis=dict(visible=False, range=[0, 115]), yaxis_title=None,
        plot_bgcolor="white", paper_bgcolor="white", height=200,
    )

    delivery_legend = html.Div([
        html.Div([
            html.Span(className="legend-dot", style={"background": "#FF7A1A"}),
            html.Span("Livrées à l'heure", className="legend-label"),
            html.Span(f"{on_time:.1f}%", className="legend-value"),
        ], className="legend-row"),
        html.Div([
            html.Span(className="legend-dot", style={"background": "#FFD9B3"}),
            html.Span("Livrées en retard", className="legend-label"),
            html.Span(f"{late:.1f}%", className="legend-value"),
        ], className="legend-row"),
        html.Div([
            html.Span(className="legend-dot", style={"background": "#FFF1E6"}),
            html.Span("Nb à l'heure", className="legend-label"),
            html.Span(f"{nb_a_lheure:,}", className="legend-value"),
        ], className="legend-row"),
        html.Div([
            html.Span(className="legend-dot", style={"background": "#F0EEEB"}),
            html.Span("Nb en retard", className="legend-label"),
            html.Span(f"{nb_en_retard:,}", className="legend-value"),
        ], className="legend-row"),
    ])

    charts = html.Div(
        [
            dbc.Row(
                [
                    dbc.Col(
                        chart_card("Revenue Analytics", "Évolution mensuelle du CA (R$)",
                                   dcc.Graph(figure=fig_revenue, config={"displayModeBar": False})),
                        md=8,
                    ),
                    dbc.Col(
                        chart_card("Monthly Target", "Commandes livrées à l'heure",
                                    # dcc.Graph(figure=fig_gauge, config={"displayModeBar": False})),
                                   html.Div([
                                       dcc.Graph(figure=fig_gauge, config={"displayModeBar": False}),
                                       gauge_legend,
                                   ])),
                        md=4,
                    ),
                ]
            ),
            dbc.Row(
                [
                    dbc.Col(
                        chart_card(
                            "Top Categories", "CA par catégorie de produit",
                            html.Div([
                                dcc.Graph(figure=fig_donut, config={"displayModeBar": False}),
                                cat_legend,
                            ]),
                        ),
                        md=4,
                    ),
                    dbc.Col(
                        chart_card("Répartition des notes", "Volume d'avis par note (1 à 5)",
                                  # dcc.Graph(figure=fig_reviews, config={"displayModeBar": False})),
                     html.Div([
                                       dcc.Graph(figure=fig_reviews, config={"displayModeBar": False}),
                                       reviews_legend,
                                   ])),
                        md=4,
                    ),
                    dbc.Col(
                        chart_card("Livraison", "Part des commandes livrées à l'heure",
                                  # dcc.Graph(figure=fig_delivery, config={"displayModeBar": False})),

                                   html.Div([
                                       dcc.Graph(figure=fig_delivery, config={"displayModeBar": False}),
                                       delivery_legend,
                                   ])),
                        md=4,
                    ),
                ]
            ),
        ]
    )

    return kpis, charts
