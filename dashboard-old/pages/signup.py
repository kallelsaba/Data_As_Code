import dash
from dash import html, dcc, Input, Output, State, callback
import dash_bootstrap_components as dbc
from auth import create_user

dash.register_page(__name__, path="/signup", name="Inscription")

layout = html.Div(
    html.Div(
        [
            html.H2("Créer un compte"),
            html.Div("Rejoignez le dashboard Olist", className="subtitle"),
            html.Div(id="signup-message", className="auth-error"),
            dbc.Input(id="signup-username", placeholder="Nom d'utilisateur", className="auth-input"),
            dbc.Input(id="signup-password", placeholder="Mot de passe", type="password", className="auth-input"),
            dbc.Button("Créer le compte", id="signup-btn", className="auth-btn", n_clicks=0),
            html.Div(
                ["Déjà un compte ? ", dcc.Link("Se connecter", href="/login", className="auth-link")],
                style={"marginTop": "18px", "fontSize": "14px", "textAlign": "center"},
            ),
        ],
        className="auth-card",
    ),
    className="auth-wrapper",
)


@callback(
    Output("signup-message", "children"),
    Input("signup-btn", "n_clicks"),
    State("signup-username", "value"),
    State("signup-password", "value"),
    prevent_initial_call=True,
)
def do_signup(n_clicks, username, password):
    ok, msg = create_user(username, password)
    if ok:
        return dcc.Link("Compte créé ! Se connecter →", href="/login", className="auth-link")
    return msg
