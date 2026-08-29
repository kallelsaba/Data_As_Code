import dash
from dash import html, dcc, Input, Output, State, callback
import dash_bootstrap_components as dbc
from auth import verify_user

dash.register_page(__name__, path="/login", name="Connexion")

layout = html.Div(
    html.Div(
        [
            html.H2("Connexion"),
            html.Div("Accédez à votre dashboard Olist", className="subtitle"),
            html.Div(id="login-error", className="auth-error"),
            dbc.Input(id="login-username", placeholder="Nom d'utilisateur", className="auth-input"),
            dbc.Input(id="login-password", placeholder="Mot de passe", type="password", className="auth-input"),
            dbc.Button("Se connecter", id="login-btn", className="auth-btn", n_clicks=0),
            html.Div(
                ["Pas encore de compte ? ", dcc.Link("Créer un compte", href="/signup", className="auth-link")],
                style={"marginTop": "18px", "fontSize": "14px", "textAlign": "center"},
            ),
        ],
        className="auth-card",
    ),
    className="auth-wrapper",
)


@callback(
    Output("auth-store", "data"),
    Output("login-error", "children"),
    Input("login-btn", "n_clicks"),
    State("login-username", "value"),
    State("login-password", "value"),
    prevent_initial_call=True,
)
def do_login(n_clicks, username, password):
    if not username or not password:
        return dash.no_update, "Merci de remplir tous les champs."
    if verify_user(username, password):
        return {"logged_in": True, "username": username}, ""
    return dash.no_update, "Identifiants incorrects."
