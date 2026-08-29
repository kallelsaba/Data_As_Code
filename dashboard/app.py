import dash
from dash import html, dcc, Input, Output, State
import dash_bootstrap_components as dbc

app = dash.Dash(
    __name__,
    use_pages=True,
    external_stylesheets=[
        dbc.themes.BOOTSTRAP,
        "https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.css",
        "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap",
    ],
    suppress_callback_exceptions=True,
)
app.title = "Olist Analytics"
server = app.server

AUTH_PAGES = ["/login", "/signup"]

NAV_ITEMS = [
    {"path": "/", "name": "Accueil", "icon": "bi-grid-1x2-fill"},
    {"path": "/ca", "name": "Chiffre d'affaires", "icon": "bi-cash-coin"},
    {"path": "/livraison", "name": "Livraison", "icon": "bi-truck"},
    {"path": "/satisfaction", "name": "Satisfaction", "icon": "bi-star-fill"},
    {"path": "/produits", "name": "Produits", "icon": "bi-box-seam"},
]


def build_sidebar(pathname):
    links = []
    for item in NAV_ITEMS:
        active = " active" if pathname == item["path"] else ""
        links.append(
            dcc.Link(
                [html.I(className=f"bi {item['icon']} me-2"), item["name"]],
                href=item["path"],
                className=f"sidebar-link{active}",
            )
        )
    return html.Div(
        [
            html.Div(
                [
                    html.Div("O", className="sidebar-logo-badge"),
                    html.Span("Olist Analytics", style={"fontWeight": "700"}),
                ],
                className="sidebar-logo",
            ),
            html.Div(links),
            html.Hr(),
            dcc.Link(
                [html.I(className="bi bi-box-arrow-right me-2"), "Déconnexion"],
                href="#",
                id="logout-link",
                className="sidebar-link",
            ),
        ],
        className="app-sidebar",
    )


def build_topbar():
    return html.Div(
        [
            html.H3("Dashboard"),
            html.Div(
                [
                    html.Div(
                        [html.I(className="bi bi-search me-2"), "Rechercher..."],
                        className="topbar-search",
                    ),
                    html.Div(
                        [
                            html.I(className="bi bi-person-circle", style={"fontSize": "20px"}),
                            html.Span(id="topbar-username"),
                        ],
                        className="user-chip",
                    ),
                ],
                style={"display": "flex", "gap": "16px", "alignItems": "center"},
            ),
        ],
        className="app-topbar",
    )


app.layout = html.Div(
    [
        dcc.Location(id="url", refresh=False),
        dcc.Store(id="auth-store", storage_type="session"),
        html.Div(id="layout-wrapper", children=dash.page_container),
        # Temporary debug badge (visible bottom-right) to inspect auth + pathname
        html.Div(id="debug-store", style={
            "position": "fixed",
            "right": "12px",
            "bottom": "12px",
            "zIndex": "9999",
            "background": "rgba(0,0,0,0.6)",
            "color": "white",
            "padding": "8px 10px",
            "borderRadius": "18px",
            "fontSize": "12px",
            "maxWidth": "320px",
            "whiteSpace": "nowrap",
            "overflow": "hidden",
            "textOverflow": "ellipsis",
        }),
    ]
)


@app.callback(
    Output("layout-wrapper", "children"),
    Input("url", "pathname"),
    Input("auth-store", "data"),
)
def render_layout(pathname, auth):
    if auth is None:
        raise dash.exceptions.PreventUpdate
    logged_in = bool(auth and auth.get("logged_in"))
    if not logged_in:
        return dash.page_container
    return dbc.Row(
        [
            dbc.Col(build_sidebar(pathname), width=2, className="p-0"),
            dbc.Col(
                [build_topbar(), html.Div(dash.page_container, className="app-content")],
                width=10,
            ),
        ],
        className="g-0",
    )


@app.callback(
    Output("url", "pathname"),
    Input("url", "pathname"),
    Input("auth-store", "data"),
    prevent_initial_call=False,
)
def guard(pathname, auth):
    # If `auth` is None it means the browser session store hasn't
    # been populated yet (race at page load). Don't force a redirect
    # in that case to avoid removing the sidebar transiently.
    if auth is None:
        raise dash.exceptions.PreventUpdate

    logged_in = bool(auth and auth.get("logged_in"))
    if not logged_in and pathname not in AUTH_PAGES:
        return "/login"
    if logged_in and pathname in AUTH_PAGES:
        return "/"
    raise dash.exceptions.PreventUpdate


@app.callback(
    Output("topbar-username", "children"),
    Input("auth-store", "data"),
)
def show_username(auth):
    if auth and auth.get("username"):
        return auth["username"]
    return dash.no_update


@app.callback(
    Output("auth-store", "data", allow_duplicate=True),
    Input("logout-link", "n_clicks"),
    prevent_initial_call=True,
)
def logout(n_clicks):
    if not n_clicks:
        raise dash.exceptions.PreventUpdate
    return {"logged_in": False}


@app.callback(
    Output("debug-store", "children"),
    Input("auth-store", "data"),
    Input("url", "pathname"),
)
def show_debug(auth, pathname):
    import json
    try:
        a = json.dumps(auth)
    except Exception:
        a = str(auth)
    return f"path={pathname} | auth={a}"


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8050)
