"""Hiérarchie d'exceptions de l'application.

Chaque erreur porte un message destiné à l'utilisateur (français, sans
jargon) ; le détail technique part dans les journaux.
"""


class FaceAnalyseError(Exception):
    """Erreur applicative de base."""

    user_message = "Une erreur inattendue est survenue."

    def __init__(self, message: str | None = None):
        super().__init__(message or self.user_message)
        if message:
            self.user_message = message


class ModelError(FaceAnalyseError):
    user_message = "Modèle de reconnaissance indisponible ou corrompu."


class ImageError(FaceAnalyseError):
    user_message = "Image illisible ou format non pris en charge."


class NoFaceError(FaceAnalyseError):
    user_message = "Aucun visage détecté dans l'image."


class DatabaseError(FaceAnalyseError):
    user_message = "Erreur d'accès à la base de données locale."


class ConsentError(FaceAnalyseError):
    user_message = "Le consentement explicite de la personne est obligatoire."


class CameraError(FaceAnalyseError):
    user_message = "Caméra indisponible."


class OsintError(FaceAnalyseError):
    user_message = "La recherche OSINT a échoué."


class AuthError(FaceAnalyseError):
    user_message = "Erreur d'authentification."


class ServerUnavailableError(AuthError):
    user_message = "Serveur de comptes injoignable."
