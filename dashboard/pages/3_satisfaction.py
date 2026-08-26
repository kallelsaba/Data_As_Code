import dash

from dash import html, dcc, Input, Output

import plotly.express as px

from db import query


dash.register_page(
    __name__,
    path="/satisfaction",
    name="Satisfaction"
)


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

    score_counts = (
        df["review_score"]
        .value_counts()
        .sort_index()
        .reset_index()
    )

    score_counts.columns = ["review_score", "count"]

    fig1 = px.pie(
        score_counts,
        names="review_score",
        values="count",
        title="Répartition des notes clients (1-5)",
        template="plotly_dark",
        hole=0.4
    )

    fig2 = px.bar(
        score_counts,
        x="review_score",
        y="count",
        title="Nombre d'avis par note",
        template="plotly_dark"
    )

    return avg_score, pct_positive, pct_negative, fig1, fig2


def layout():
    return html.Div([

        html.H2("⭐ Satisfaction client"),

        html.Div(
            id="satisfaction-kpis",
            className="mb-4"
        ),

        dcc.Graph(
            id="satisfaction-pie"
        ),

        dcc.Graph(
            id="satisfaction-bar"
        ),

        dcc.Interval(
            id="satisfaction-refresh",
            interval=5 * 60 * 1000,
            n_intervals=0
        )
    ])


@dash.callback(
    Output("satisfaction-kpis", "children"),
    Output("satisfaction-pie", "figure"),
    Output("satisfaction-bar", "figure"),
    Input("satisfaction-refresh", "n_intervals")
)
def update_satisfaction(n_intervals):

    df = get_data()

    avg_score, pct_positive, pct_negative, fig1, fig2 = build_figures(df)

    kpis = html.Div([
        html.Div(
            f"Note moyenne: {avg_score:.2f}/5",
            className="badge bg-warning text-dark fs-5 me-3"
        ),

        html.Div(
            f"Avis positifs: {pct_positive:.1f}%",
            className="badge bg-success fs-5 me-3"
        ),

        html.Div(
            f"Avis négatifs: {pct_negative:.1f}%",
            className="badge bg-danger fs-5"
        ),
    ])

    return kpis, fig1, fig2
