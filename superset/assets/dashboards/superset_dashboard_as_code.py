"""
Dashboard as Code — DataOps Olist
=================================

Superset 6.1.0

Crée / met à jour :
- 1 base de données
- 4 datasets virtuels
- les charts
- 1 dashboard unique

Disposition :

Chiffre d'affaires
    Ligne 1 : Évolution du CA mensuel | CA total
    Ligne 2 : Panier moyen             | Nombre de commandes

Livraison
    Ligne 1 : Délai moyen              | % livré à l'heure
    Ligne 2 : Délai moyen par mois     | Distribution des retards/avances

Satisfaction
    Ligne 1 : Note moyenne | % avis positifs | % avis négatifs
    Ligne 2 : Répartition des notes

Produits
    Ligne 1 : Top 10 catégories par CA
    Ligne 2 : Top 10 catégories par ventes

Le script est idempotent :
- il recherche les objets existants par nom
- il les met à jour
- il ne crée pas volontairement de doublons
"""

import json
import requests


# ================================================================
# CONFIGURATION
# ================================================================

SUPERSET_URL = "http://superset:8088"

USERNAME = "admin"
PASSWORD = "admin"

DB_NAME = "PostgreSQL DataOps"

SQLALCHEMY_URI = (
    "postgresql+psycopg2://dataops:dataops@postgres:5432/dataops"
)

DASHBOARD_TITLE = "DataOps Olist — Pilotage"

session = requests.Session()


# ================================================================
# AUTHENTIFICATION
# ================================================================

def login():
    print("Connexion à Superset...")

    resp = session.post(
        f"{SUPERSET_URL}/api/v1/security/login",
        json={
            "username": USERNAME,
            "password": PASSWORD,
            "provider": "db",
            "refresh": True,
        },
    )

    resp.raise_for_status()

    token = resp.json()["access_token"]

    session.headers.update({
        "Authorization": f"Bearer {token}",
    })

    csrf = session.get(
        f"{SUPERSET_URL}/api/v1/security/csrf_token/"
    )

    csrf.raise_for_status()

    session.headers.update({
        "X-CSRFToken": csrf.json()["result"],
        "Referer": SUPERSET_URL,
    })

    print("Connexion OK")


# ================================================================
# RECHERCHE PAR NOM
# ================================================================

def find_by_name(endpoint, name_field, name_value):
    """
    Recherche un objet Superset par son nom.
    """

    safe_value = str(name_value).replace("'", "")

    q = (
        f"(filters:!((col:{name_field},"
        f"opr:eq,value:'{safe_value}')))"
    )

    resp = session.get(
        f"{SUPERSET_URL}/api/v1/{endpoint}/?q={q}"
    )

    resp.raise_for_status()

    result = resp.json().get("result", [])

    if result:
        return result[0]["id"]

    return None


# ================================================================
# DATABASE
# ================================================================

def get_or_create_database():

    db_id = find_by_name(
        "database",
        "database_name",
        DB_NAME,
    )

    if db_id:
        print(f"Database existante : {db_id}")
        return db_id

    print("Création de la database...")

    resp = session.post(
        f"{SUPERSET_URL}/api/v1/database/",
        json={
            "database_name": DB_NAME,
            "sqlalchemy_uri": SQLALCHEMY_URI,
            "expose_in_sqllab": True,
        },
    )

    resp.raise_for_status()

    db_id = resp.json()["id"]

    print(f"Database créée : {db_id}")

    return db_id


# ================================================================
# DATASETS
# ================================================================

def get_or_create_dataset(db_id, table_name, sql):

    ds_id = find_by_name(
        "dataset",
        "table_name",
        table_name,
    )

    if ds_id:

        print(
            f"Dataset existant : {table_name} "
            f"(id={ds_id})"
        )

        resp = session.put(
            f"{SUPERSET_URL}/api/v1/dataset/{ds_id}",
            json={
                "table_name": table_name,
                "sql": sql,
                "schema": "silver",
            },
        )

        resp.raise_for_status()

        return ds_id

    print(f"Création dataset : {table_name}")

    resp = session.post(
        f"{SUPERSET_URL}/api/v1/dataset/",
        json={
            "database": db_id,
            "table_name": table_name,
            "sql": sql,
            "schema": "silver",
        },
    )

    resp.raise_for_status()

    ds_id = resp.json()["id"]

    print(
        f"Dataset créé : {table_name} "
        f"(id={ds_id})"
    )

    return ds_id


# ================================================================
# CHARTS
# ================================================================

def get_or_create_chart(
    name,
    viz_type,
    dataset_id,
    params,
):

    chart_id = find_by_name(
        "chart",
        "slice_name",
        name,
    )

    payload = {
        "slice_name": name,
        "viz_type": viz_type,
        "datasource_id": dataset_id,
        "datasource_type": "table",
        "params": json.dumps(
            params,
            ensure_ascii=False,
        ),
    }

    # ------------------------------------------------------------
    # UPDATE
    # ------------------------------------------------------------

    if chart_id:

        print(
            f"Chart existant : {name} "
            f"(id={chart_id})"
        )

        resp = session.put(
            f"{SUPERSET_URL}/api/v1/chart/{chart_id}",
            json=payload,
        )

        if not resp.ok:

            print("")
            print("========================================")
            print("ERREUR SUPSERSET")
            print("========================================")
            print("Chart :", name)
            print("ID :", chart_id)
            print("STATUS :", resp.status_code)
            print("RESPONSE :", resp.text)
            print("PAYLOAD :", payload)
            print("========================================")
            print("")

            resp.raise_for_status()

        return chart_id

    # ------------------------------------------------------------
    # CREATE
    # ------------------------------------------------------------

    print(f"Création chart : {name}")

    resp = session.post(
        f"{SUPERSET_URL}/api/v1/chart/",
        json=payload,
    )

    if not resp.ok:

        print("")
        print("========================================")
        print("ERREUR SUPSERSET")
        print("========================================")
        print("Chart :", name)
        print("STATUS :", resp.status_code)
        print("RESPONSE :", resp.text)
        print("PAYLOAD :", payload)
        print("========================================")
        print("")

        resp.raise_for_status()

    return resp.json()["id"]


# ================================================================
# LAYOUT DU DASHBOARD
# ================================================================

def build_position_json(sections):

    """
    sections :

    {
        "Nom section": [
            [chart_id, chart_id],
            [chart_id, chart_id],
        ]
    }

    Chaque liste interne représente UNE ligne.
    """

    layout = {
        "DASHBOARD_VERSION_KEY": "v2",

        "ROOT_ID": {
            "type": "ROOT",
            "id": "ROOT_ID",
            "children": ["GRID_ID"],
        },

        "GRID_ID": {
            "type": "GRID",
            "id": "GRID_ID",
            "children": [],
            "parents": ["ROOT_ID"],
        },
    }

    row_counter = 0

    for section_name, rows in sections.items():

        # --------------------------------------------------------
        # TITRE DE SECTION
        # --------------------------------------------------------

        row_counter += 1

        header_row_id = (
            f"ROW-header-{row_counter}"
        )

        markdown_id = (
            f"MARKDOWN-{row_counter}"
        )

        layout["GRID_ID"]["children"].append(
            header_row_id
        )

        layout[header_row_id] = {
            "type": "ROW",
            "id": header_row_id,
            "children": [markdown_id],
            "parents": [
                "ROOT_ID",
                "GRID_ID",
            ],
            "meta": {
                "background":
                    "BACKGROUND_TRANSPARENT"
            },
        }

        layout[markdown_id] = {
            "type": "MARKDOWN",
            "id": markdown_id,
            "children": [],
            "parents": [
                "ROOT_ID",
                "GRID_ID",
                header_row_id,
            ],
            "meta": {
                "width": 12,
                "height": 8,
                "code": f"## {section_name}",
            },
        }

        # --------------------------------------------------------
        # LIGNES DE CHARTS
        # --------------------------------------------------------

        for row_charts in rows:

            if not row_charts:
                continue

            row_counter += 1

            row_id = f"ROW-{row_counter}"

            layout["GRID_ID"]["children"].append(
                row_id
            )

            layout[row_id] = {
                "type": "ROW",
                "id": row_id,
                "children": [],
                "parents": [
                    "ROOT_ID",
                    "GRID_ID",
                ],
                "meta": {
                    "background":
                        "BACKGROUND_TRANSPARENT"
                },
            }

            width = 12 // len(row_charts)

            for cid in row_charts:

                chart_key = f"CHART-{cid}"

                layout[row_id]["children"].append(
                    chart_key
                )

                layout[chart_key] = {
                    "type": "CHART",
                    "id": chart_key,
                    "children": [],
                    "parents": [
                        "ROOT_ID",
                        "GRID_ID",
                        row_id,
                    ],
                    "meta": {
                        "width": width,
                        "height": 50,
                        "chartId": cid,
                        "sliceName": str(cid),
                    },
                }

    return json.dumps(
        layout,
        ensure_ascii=False,
    )


# ================================================================
# DASHBOARD
# ================================================================

def get_or_create_dashboard(
    title,
    chart_ids,
    tabs_layout,
):

    dash_id = find_by_name(
        "dashboard",
        "dashboard_title",
        title,
    )

    payload = {
        "dashboard_title": title,

        "position_json": build_position_json(
            tabs_layout
        ),

        "published": True,

        "json_metadata": json.dumps({
            "refresh_frequency": 300
        }),
    }

    # ------------------------------------------------------------
    # UPDATE DASHBOARD
    # ------------------------------------------------------------

    if dash_id:

        print(
            f"Dashboard existant : {dash_id}"
        )

        resp = session.put(
            f"{SUPERSET_URL}/api/v1/dashboard/{dash_id}",
            json=payload,
        )

        resp.raise_for_status()

    # ------------------------------------------------------------
    # CREATE DASHBOARD
    # ------------------------------------------------------------

    else:

        print("Création du dashboard...")

        resp = session.post(
            f"{SUPERSET_URL}/api/v1/dashboard/",
            json=payload,
        )

        resp.raise_for_status()

        dash_id = resp.json()["id"]

    # ------------------------------------------------------------
    # ASSOCIER LES CHARTS AU DASHBOARD
    # ------------------------------------------------------------

    for cid in chart_ids:

        resp = session.put(
            f"{SUPERSET_URL}/api/v1/chart/{cid}",
            json={
                "dashboards": [dash_id]
            },
        )

        if not resp.ok:
            print(
                f"Attention association chart "
                f"{cid} -> dashboard impossible : "
                f"{resp.status_code}"
            )

    return dash_id


# ================================================================
# DATASETS SQL
# ================================================================

SQL_CA = """
SELECT DISTINCT
    order_id,
    order_purchase_timestamp,
    order_total_value
FROM silver.stg_orders
WHERE order_purchase_timestamp IS NOT NULL
"""


SQL_LIVRAISON = """
SELECT DISTINCT
    order_id,
    order_purchase_timestamp,
    total_delivery_days,
    delivery_delay_days,
    is_delivered_on_time
FROM silver.stg_orders
WHERE total_delivery_days IS NOT NULL
"""


SQL_SATISFACTION = """
SELECT DISTINCT
    order_id,
    review_score,
    is_positive_review,
    is_negative_review,
    has_comment
FROM silver.stg_orders
WHERE review_score IS NOT NULL
"""


SQL_PRODUITS = """
SELECT
    product_category_name,
    price,
    freight_value
FROM silver.stg_orders
WHERE product_category_name IS NOT NULL
"""


# ================================================================
# MAIN
# ================================================================

def main():

    print("")
    print("========================================")
    print(" DATAOPS OLIST — DASHBOARD AS CODE")
    print(" SUPSERSET 6.1.0")
    print("========================================")
    print("")

    # ------------------------------------------------------------
    # LOGIN
    # ------------------------------------------------------------

    login()

    # ------------------------------------------------------------
    # DATABASE
    # ------------------------------------------------------------

    db_id = get_or_create_database()

    # ------------------------------------------------------------
    # DATASETS
    # ------------------------------------------------------------

    ds_ca = get_or_create_dataset(
        db_id,
        "vw_ca",
        SQL_CA,
    )

    ds_liv = get_or_create_dataset(
        db_id,
        "vw_livraison",
        SQL_LIVRAISON,
    )

    ds_sat = get_or_create_dataset(
        db_id,
        "vw_satisfaction",
        SQL_SATISFACTION,
    )

    ds_prod = get_or_create_dataset(
        db_id,
        "vw_produits",
        SQL_PRODUITS,
    )

    # ============================================================
    # CHIFFRE D'AFFAIRES
    # ============================================================

    c_ca_total = get_or_create_chart(
        "CA total",
        "big_number_total",
        ds_ca,
        {
            "metric": {
                "expressionType": "SQL",
                "sqlExpression":
                    "SUM(order_total_value)",
                "label": "CA total",
            }
        },
    )

    c_ca_nb = get_or_create_chart(
        "Nombre de commandes",
        "big_number_total",
        ds_ca,
        {
            "metric": {
                "expressionType": "SQL",
                "sqlExpression":
                    "COUNT(DISTINCT order_id)",
                "label": "Nombre de commandes",
            }
        },
    )

    c_ca_avg = get_or_create_chart(
        "Panier moyen",
        "big_number_total",
        ds_ca,
        {
            "metric": {
                "expressionType": "SQL",
                "sqlExpression":
                    "AVG(order_total_value)",
                "label": "Panier moyen",
            }
        },
    )

    c_ca_trend = get_or_create_chart(
        "Évolution du CA mensuel",
        "echarts_timeseries_line",
        ds_ca,
        {
            "x_axis":
                "order_purchase_timestamp",

            "time_grain_sqla":
                "P1M",

            "metrics": [
                {
                    "expressionType": "SQL",
                    "sqlExpression":
                        "SUM(order_total_value)",
                    "label": "CA",
                }
            ],

            "row_limit": 10000,
        },
    )

    # ============================================================
    # LIVRAISON
    # ============================================================

    c_liv_avg = get_or_create_chart(
        "Délai moyen de livraison",
        "big_number_total",
        ds_liv,
        {
            "metric": {
                "expressionType": "SQL",
                "sqlExpression":
                    "AVG(total_delivery_days)",
                "label":
                    "Délai moyen de livraison",
            }
        },
    )

    c_liv_ontime = get_or_create_chart(
        "% livré à l'heure",
        "big_number_total",
        ds_liv,
        {
            "metric": {
                "expressionType": "SQL",

                "sqlExpression": (
                    "100.0 * SUM("
                    "CASE "
                    "WHEN is_delivered_on_time = TRUE "
                    "THEN 1 "
                    "ELSE 0 "
                    "END"
                    ") / NULLIF(COUNT(*), 0)"
                ),

                "label":
                    "% livré à l'heure",
            }
        },
    )

    c_liv_trend = get_or_create_chart(
        "Délai moyen par mois",
        "echarts_timeseries_line",
        ds_liv,
        {
            "x_axis":
                "order_purchase_timestamp",

            "time_grain_sqla":
                "P1M",

            "metrics": [
                {
                    "expressionType": "SQL",
                    "sqlExpression":
                        "AVG(total_delivery_days)",
                    "label":
                        "Délai moyen",
                }
            ],

            "row_limit": 10000,
        },
    )

    c_liv_hist = get_or_create_chart(
        "Distribution des retards/avances",
        "echarts_timeseries_bar",
        ds_liv,
        {
            "x_axis":
                "order_purchase_timestamp",

            "time_grain_sqla":
                "P1M",

            "metrics": [
                {
                    "expressionType": "SQL",
                    "sqlExpression":
                        "AVG(delivery_delay_days)",
                    "label":
                        "Retard moyen",
                }
            ],

            "row_limit": 100,
        },
    )

    # ============================================================
    # SATISFACTION
    # ============================================================

    c_sat_avg = get_or_create_chart(
        "Note moyenne",
        "big_number_total",
        ds_sat,
        {
            "metric": {
                "expressionType": "SQL",
                "sqlExpression":
                    "AVG(review_score)",
                "label": "Note moyenne",
            }
        },
    )

    c_sat_pos = get_or_create_chart(
        "% avis positifs",
        "big_number_total",
        ds_sat,
        {
            "metric": {
                "expressionType": "SQL",
                "sqlExpression": (
                    "AVG("
                    "CASE "
                    "WHEN is_positive_review = TRUE "
                    "THEN 100.0 "
                    "ELSE 0 "
                    "END"
                    ")"
                ),
                "label": "% avis positifs",
            }
        },
    )

    c_sat_neg = get_or_create_chart(
        "% avis négatifs",
        "big_number_total",
        ds_sat,
        {
            "metric": {
                "expressionType": "SQL",
                "sqlExpression": (
                    "AVG("
                    "CASE "
                    "WHEN is_negative_review = TRUE "
                    "THEN 100.0 "
                    "ELSE 0 "
                    "END"
                    ")"
                ),
                "label": "% avis négatifs",
            }
        },
    )

    c_sat_bar = get_or_create_chart(
        "Nombre d'avis par note",
        "pie",
        ds_sat,
        {
            "groupby": [
                "review_score"
            ],

            "metric": "count",

            "row_limit": 10,
        },
    )

    # ============================================================
    # PRODUITS
    # ============================================================

    c_prod_ca = get_or_create_chart(
        "Top 10 catégories par CA",
        "pie",
        ds_prod,
        {
            "groupby": [
                "product_category_name"
            ],

            "metric": {
                "expressionType": "SQL",
                "sqlExpression":
                    "SUM(price)",
                "label": "CA",
            },

            "row_limit": 10,
        },
    )

    c_prod_nb = get_or_create_chart(
        "Top 10 catégories par ventes",
        "pie",
        ds_prod,
        {
            "groupby": [
                "product_category_name"
            ],

            "metric": {
                "expressionType": "SQL",
                "sqlExpression":
                    "COUNT(*)",
                "label": "Ventes",
            },

            "row_limit": 10,
        },
    )

    # ============================================================
    # LAYOUT
    # ============================================================

    tabs_layout = {

        "Chiffre d'affaires": [

            # Ligne 1
            [
                c_ca_trend,
                c_ca_total,
            ],

            # Ligne 2
            [
                c_ca_avg,
                c_ca_nb,
            ],
        ],

        "Livraison": [

            # Ligne 1
            [
                c_liv_avg,
                c_liv_ontime,
            ],

            # Ligne 2
            [
                c_liv_trend,
                c_liv_hist,
            ],
        ],

        "Satisfaction": [

            # Ligne 1
            [
                c_sat_avg,
                c_sat_pos,
                c_sat_neg,
            ],

            # Ligne 2
            [
                c_sat_bar,
            ],
        ],

        "Produits": [

            # Ligne 1
            [
                c_prod_ca,
            ],

            # Ligne 2
            [
                c_prod_nb,
            ],
        ],
    }

    # ============================================================
    # TOUS LES CHARTS
    # ============================================================

    all_charts = [
        cid
        for rows in tabs_layout.values()
        for row in rows
        for cid in row
    ]

    # Supprime les éventuels doublons
    all_charts = list(dict.fromkeys(all_charts))

    # ============================================================
    # DASHBOARD
    # ============================================================

    dash_id = get_or_create_dashboard(
        DASHBOARD_TITLE,
        all_charts,
        tabs_layout,
    )

    # ============================================================
    # FIN
    # ============================================================

    print("")
    print("========================================")
    print(" DASHBOARD PRÊT")
    print("========================================")
    print(
        f"Dashboard ID : {dash_id}"
    )
    print(
        f"URL : {SUPERSET_URL}/superset/dashboard/{dash_id}/"
    )
    print("========================================")
    print("")


if __name__ == "__main__":
    main()
