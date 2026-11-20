# FACE ANALYSE — Serveur de comptes & administration

Ce serveur est le **coffre** du projet. L'application de bureau ne fonctionne que
si un compte validé par ce serveur l'autorise. Vous gardez le contrôle : vous
pouvez suspendre un compte ou révoquer une session **à distance**, et consulter
qui est connecté, depuis quelle machine et quelle IP.

> **Protection du projet.** Un `.exe` peut toujours être décompilé. La vraie
> protection vient d'ici : tant que vous ne distribuez pas ce serveur ni ses
> secrets, personne ne peut créer de session valide ni utiliser l'app « pour de
> vrai ». Changez `FA_SECRET_KEY`, gardez la base `server.db` privée.

> **Transparence (RGPD).** La journalisation est **affichée aux utilisateurs** au
> moment de la connexion (écran de consentement). Ne retirez pas cet écran : la
> collecte d'IP, de machine et d'activité sans information est illégale.

## Démarrage rapide

```bash
cd server
python -m pip install -r requirements.txt
export FA_SECRET_KEY="$(python -c 'import secrets;print(secrets.token_urlsafe(48))')"
export FA_ADMIN_EMAIL="vous@exemple.com"
export FA_ADMIN_PASSWORD="un-mot-de-passe-solide"
python run.py
```

Ouvrez **http://localhost:8000/admin** et connectez-vous avec le compte admin.

## Variables d'environnement

| Variable | Rôle |
|---|---|
| `FA_SECRET_KEY` | **obligatoire en prod** : signe les états OAuth. Gardez-la secrète et stable. |
| `FA_ADMIN_EMAIL` / `FA_ADMIN_PASSWORD` | crée/promeut votre compte propriétaire au démarrage |
| `FA_PUBLIC_URL` | URL publique du serveur (ex. `https://panel.mondomaine.fr`) — indispensable pour l'OAuth |
| `FA_OPEN_REGISTRATION` | `true` (défaut) : inscriptions ouvertes ; `false` : seul l'admin crée les comptes |
| `FA_TRUST_PROXY` | `true` si derrière un reverse-proxy (lit `X-Forwarded-For`) |
| `FA_DISCORD_CLIENT_ID` / `FA_DISCORD_CLIENT_SECRET` | active « Se connecter avec Discord » |
| `FA_GOOGLE_CLIENT_ID` / `FA_GOOGLE_CLIENT_SECRET` | active « Se connecter avec Google » |
| `FA_DB_URL` | défaut : SQLite local. Accepte PostgreSQL (`postgresql+psycopg://…`) |
| `FA_DATA_DIR` | dossier des données (base, etc.) |

### OAuth Discord
1. https://discord.com/developers/applications → New Application → OAuth2.
2. Redirect : `FA_PUBLIC_URL/auth/discord/callback`.
3. Copiez *Client ID* et *Client Secret* dans les variables ci-dessus.

### OAuth Google
1. https://console.cloud.google.com/ → *APIs & Services* → *Credentials* → *OAuth client ID* (type Web).
2. Redirect URI autorisé : `FA_PUBLIC_URL/auth/google/callback`.
3. Copiez *Client ID* et *Client Secret*.

## Relier l'application de bureau

Dans l'app (SETTINGS → Compte & accès) ou via la variable `FACE_ANALYSE_SERVER`,
indiquez l'URL du serveur. L'app exigera alors une connexion et enverra
battements de cœur et événements. Sans URL de serveur, l'app fonctionne en mode
autonome (sans comptes).

## Sécurité de déploiement
* Mettez-le **derrière HTTPS** (reverse-proxy : Caddy, Nginx, Traefik) et activez `FA_TRUST_PROXY`.
* Sauvegardez `server.db`. Ne le committez jamais.
* Mots de passe hachés PBKDF2-HMAC-SHA256 (210 000 itérations). Jetons de session
  aléatoires, stockés hachés (SHA-256) : une fuite de base ne révèle pas les jetons.
