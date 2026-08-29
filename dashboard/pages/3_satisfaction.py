import dash
from dash import html, dcc, Input, Output, callback
import dash_bootstrap_components as dbc
import plotly.express as px
from db import query
from components import kpi_card, chart_card

dash.register_page(__name__, path="/satisfaction", name="Satisfaction")

ORANGE_SCALE = ["#FFD9B3", "#FFB877", "#FF9A47", "#FF7A1A", "#E86A0C"]


def get_data():
    sql = """
        SELECT DISTINCT
            order_id,
            review_score,
            is_positive_review,
            is_negative_review,
            has_comment
        FROM silver.stg_orders
        WHERE review_score IS NOT NULL
    """
    return query(sql)


def build_figures(df):
    avg_score = df["review_score"].mean()
    pct_positive = df["is_positive_review"].mean() * 100
    pct_negative = df["is_negative_review"].mean() * 100

    score_counts = df["review_score"].value_counts().sort_index().reset_index()
    score_counts.columns = ["review_score", "count"]

    fig1 = px.pie(
        score_counts, names="review_score", values="count", hole=0.55,
        color_discrete_sequence=ORANGE_SCALE,
    )
    fig1.update_layout(margin=dict(l=10, r=10, t=10, b=10), plot_bgcolor="white", paper_bgcolor="white")

    fig2 = px.bar(score_counts, x="review_score", y="count", color_discrete_sequence=["#FF7A1A"])
    fig2.update_layout(
        template="plotly_white", margin=dict(l=10, r=10, t=10, b=10),
        xaxis_title="Note", yaxis_title="Nombre d'avis", plot_bgcolor="white", paper_bgcolor="white",
    )

    return avg_score, pct_positive, pct_negative, fig1, fig2


layout = html.Div(
    [
        html.Div(id="satisfaction-content"),
        dcc.Interval(id="satisfaction-refresh", interval=5 * 60 * 1000, n_intervals=0),
    ]
)


@callback(
    Output("satisfaction-content", "children"),
    Input("satisfaction-refresh", "n_intervals"),
)
def update_satisfaction(n_intervals):
    df = get_data()
    avg_score, pct_positive, pct_negative, fig1, fig2 = build_figures(df)

    kpis = dbc.Row(
        [
            kpi_card("bi-star-fill", "Note moyenne", f"{avg_score:.2f}/5", width=4),
            kpi_card("bi-emoji-smile", "Avis positifs", f"{pct_positive:.1f}%", width=4),
            kpi_card("bi-emoji-frown", "Avis négatifs", f"{pct_negative:.1f}%", width=4),
        ]
    )

    return html.Div(
        [
            kpis,
            dbc.Row(
                [
                    dbc.Col(
                        chart_card("Répartition des notes", "Notes clients de 1 à 5",
                                   dcc.Graph(figure=fig1, config={"displayModeBar": False})),
                        md=6,
                    ),
                    dbc.Col(
                        chart_card("Nombre d'avis par note", "Volume d'avis par note",
                                   dcc.Graph(figure=fig2, config={"displayModeBar": False})),
                        md=6,
                    ),
                ]
            ),
        ]
    )
