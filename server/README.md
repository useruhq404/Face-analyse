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

## Le plus simple : lancement local en 1 commande

```bash
cd server
python start_local.py
```

(Sous Windows : double-cliquez **`start_server.bat`**. Sous macOS/Linux : `./start_server.sh`.)

Au premier lancement, le script crée tout seul votre clé secrète et votre **compte
administrateur**, puis affiche :

```
  Panneau d'administration :  http://localhost:8000/admin
  e-mail       : admin@local
  mot de passe : (généré, affiché dans le terminal)
  À coller dans l'app (SETTINGS → Serveur de comptes) :  http://localhost:8000
```

Ouvrez le panel dans votre navigateur, connectez-vous, et dans l'application de
bureau collez `http://localhost:8000` dans **SETTINGS → Serveur de comptes**. Vos
identifiants sont conservés dans `fa_server_data/local_config.json`.

> **Tester depuis votre téléphone / un autre PC du même Wi-Fi :**
> `FA_HOST=0.0.0.0 python start_local.py` — le script affiche alors aussi l'adresse
> « réseau local » (ex. `http://192.168.1.20:8000`) à utiliser sur l'autre appareil.

## Démarrage manuel (variables d'environnement)

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

Pour que l'app **distribuée** exige la connexion sans réglage, mettez l'URL de
votre serveur dans `face_analyse/resources/deployment.json` **avant de compiler
l'exe** :

```json
{ "server_url": "https://panel.mondomaine.fr", "force_login": true }
```

## Passer à un vrai site accessible partout (domaine + HTTPS)

Le lancement local ne marche que sur votre machine. Pour que vos utilisateurs s'y
connectent depuis n'importe où, il faut un serveur accessible sur Internet. Marche
à suivre, quand vous serez prêt :

1. **Un petit serveur (VPS)** chez un hébergeur (Hetzner, OVH, Scaleway, DigitalOcean…),
   ~4–6 €/mois, Ubuntu. Vous obtenez une IP publique.
2. **Un nom de domaine** (OVH, Namecheap, Cloudflare…), ~10 €/an. Créez un
   enregistrement **A** `panel.votredomaine.fr → l'IP du VPS`.
3. **HTTPS automatique avec Caddy** (le plus simple) sur le VPS — fichier `Caddyfile` :

   ```
   panel.votredomaine.fr {
       reverse_proxy 127.0.0.1:8000
   }
   ```

   Caddy obtient et renouvelle le certificat TLS tout seul.
4. **Lancer le serveur** sur le VPS (derrière Caddy) avec vos variables :

   ```bash
   export FA_SECRET_KEY="…stable et secret…"
   export FA_ADMIN_EMAIL="vous@exemple.com"
   export FA_ADMIN_PASSWORD="…"
   export FA_PUBLIC_URL="https://panel.votredomaine.fr"
   export FA_TRUST_PROXY=true
   python run.py        # écoute sur 127.0.0.1:8000, Caddy expose le HTTPS
   ```

   (Pour qu'il tourne en permanence : un service **systemd**, ou `tmux`/`screen` pour commencer.)
5. **OAuth** : dans les consoles Discord/Google, mettez les URL de redirection
   `https://panel.votredomaine.fr/auth/discord/callback` et `…/auth/google/callback`.
6. **Dans l'app** : `deployment.json` → `"server_url": "https://panel.votredomaine.fr"`, recompilez l'exe.

Dites-moi quand vous en êtes là : je peux vous écrire le service systemd, le
`Caddyfile` complet et un script d'installation pour le VPS.

## Sécurité de déploiement
* Mettez-le **derrière HTTPS** (reverse-proxy : Caddy, Nginx, Traefik) et activez `FA_TRUST_PROXY`.
* Sauvegardez `server.db`. Ne le committez jamais.
* Mots de passe hachés PBKDF2-HMAC-SHA256 (210 000 itérations). Jetons de session
  aléatoires, stockés hachés (SHA-256) : une fuite de base ne révèle pas les jetons.
