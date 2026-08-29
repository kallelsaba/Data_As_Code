from dash import html
import dash_bootstrap_components as dbc


def kpi_card(icon, label, value, width=3, variant="default"):
    card_class = "kpi-card kpi-card-orange" if variant == "orange" else "kpi-card"
    return dbc.Col(
        html.Div(
            [
                html.Div(html.I(className=f"bi {icon}"), className="kpi-icon"),
                html.Div(label, className="kpi-label"),
                html.Div(value, className="kpi-value"),
            ],
            className=card_class,
        ),
        md=width, sm=6, xs=12, className="mb-4",
    )


def chart_card(title, subtitle, graph):
    return html.Div(
        [
            html.H5(title),
            html.Div(subtitle, className="subtitle"),
            graph,
        ],
        className="chart-card",
    )
