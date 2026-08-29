# Stockage des utilisateurs en mémoire (redémarre = repart avec admin/admin uniquement).
# Ceci ne touche pas à Postgres ni au pipeline de données.
USERS = {"admin": "admin"}


def verify_user(username, password):
    return bool(username) and USERS.get(username) == password


def create_user(username, password):
    if not username or not password:
        return False, "Merci de remplir tous les champs."
    if username in USERS:
        return False, "Ce nom d'utilisateur existe déjà."
    USERS[username] = password
    return True, "Compte créé avec succès."
