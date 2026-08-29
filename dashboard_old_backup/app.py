
import dash

import dash_bootstrap_components as dbc

from dash import html

app = dash.Dash(

    __name__,

    use_pages=True,

    external_stylesheets=[dbc.themes.CYBORG],

    suppress_callback_exceptions=True,

)

app.title = "Olist - Dataops Dashboard"

sidebar = dbc.Nav(

    [

        dbc.NavLink(

            [html.Div(page["name"], className="ms-2")],

            href=page["path"],

            active="exact",

        )

        for page in dash.page_registry.values()

    ],

    vertical=True,

    pills=True,

    className="bg-dark p-3",

)

app.layout = dbc.Container(

    [

        dbc.Row(

            [

                dbc.Col(

                    [

                        html.H2("Olist Analytics", className="text-white mt-3"),

                        html.Hr(),

                        sidebar,

                    ],

                    width=2,

                    className="bg-dark vh-100",

                ),

                dbc.Col(dash.page_container, width=10, className="p-4"),

            ]

        )

    ],

    fluid=True,

)

if __name__ == "__main__":

    app.run(debug=True, host="0.0.0.0", port=8050)

