"""Textes légaux (consentement, mentions). Modifiables avant déploiement."""

CONSENT_NOTICE = (
    "En vous connectant à FACE ANALYSE, vous acceptez que, pour la sécurité du service "
    "et la gestion de votre compte, les informations suivantes soient enregistrées par "
    "l'administrateur : votre pseudonyme, votre adresse e-mail (si fournie), votre adresse IP, "
    "le nom et le système de votre appareil, un identifiant technique de machine, la version de "
    "l'application, ainsi que l'horodatage de vos connexions et des principales actions réalisées "
    "dans l'application (sans le contenu de vos images ni de vos recherches). Ces données sont "
    "conservées localement sur le serveur de l'administrateur et ne sont pas revendues. "
    "Conformément au RGPD, vous pouvez demander leur consultation ou leur suppression, et retirer "
    "votre consentement en cessant d'utiliser le service."
)

DATA_COLLECTED = [
    ("Pseudonyme & avatar", "ce que vous choisissez d'afficher"),
    ("E-mail", "si vous vous inscrivez par e-mail ou via Google/Discord"),
    ("Adresse IP + géolocalisation approximative", "pays/ville, FAI — via la connexion"),
    ("Appareil", "nom de machine, système, identifiant technique, version de l'app"),
    ("Journal", "connexions, déconnexions, module ouvert et action lancée, horodatés"),
]
