# Neogrip

Contrôle d’une main/prothèse via un casque EEG (EMOTIV / Cortex) et des servomoteurs (PCA9685 / Adafruit Blinka) sur Raspberry Pi.

- Code applicatif : `neogrip/` + `main.py` :contentReference[oaicite:1]{index=1}  
- Déploiement : `install.sh` + fichiers systemd/config dans `Deploy/` :contentReference[oaicite:2]{index=2}  
- Licence : GPL-3.0

## Fonctionnement (vue d’ensemble)

1. Connexion à Cortex (WebSocket) et abonnement au flux “Mental Commands”.
2. Mapping des commandes (ex. push/pull) vers un contrôleur de main.
3. Pilotage des servos via un backend :
   - **PCA9685Backend** (réel) : I2C + Adafruit Blinka
   - **NullBackend** (simulation) : affiche les impulsions dans les logs (utile sans hardware)

## Matériel compatible (minimum)

- Raspberry Pi (testé sur Pi OS / Debian Bookworm)
- Carte PCA9685 (I2C) + servos
- Casque EEG EMOTIV EPOC X + Cortex (Emotiv Launcher)
- Câblage I2C :
  - SDA = GPIO2 (pin 3)
  - SCL = GPIO3 (pin 5)
  - GND commun

## Prérequis système

- Python 3 + `python3-venv`
- I2C activé côté Raspberry Pi
- Accès périphériques :
  - groupe `i2c` pour `/dev/i2c-*`
  - groupe `gpio` pour `/dev/gpiochip*` (Blinka/lgpio)

### Activer I2C
```bash
sudo raspi-config
# Interface Options -> I2C -> Enable
sudo reboot

# Vérification
ls -l /dev/i2c-1
sudo i2cdetect -y 1
```

## Installation (version Raspberry seulement)

### 1) Cloner le dépôt

```bash
git clone https://github.com/Neogrip/Neogrip.git
cd Neogrip
```

### 2) Lancer le script d'installation

> Utilisez `bash` (pas `sh`), le script de supporte pas la syntax shell.

```bash
sudo bash install.sh
```

Le script permet de :
- Installer les dépendances système,
- déploier l'application sous `/opt/neogrip`,
- créer un environnement virtuel Python,
- installer les dépendances (`requirements.txt`)
- déploier un service `neogrip.service`,
- mettre en place un fichier de configuration/secrets `/etc/neogrip/secrets.env`

### 3) Renseigner les secrets et la configuration

```bash
sudo nano /etc/neogrip/secrets.env
```

Variables :

- `EMOTIV_CLIENT_ID` : Numéro du compte EMOTIV (issue de l'API)
- `EMOTIV_CLIENT_SECRET` : Secret (issue de l'API)
- `EMOTIV_PROFILE` : Nom du profile d'entraînement

Exemple :

```bash
# EMOTIVS CREDS
EMOTIV_CLIENT_ID="ID_EXEMPLE"
EMOTIV_CLIENT_SECRET="SECRET_EXEMPLE"

# Config
EMOTIV_PROFILE="MON_PROFILE"
```

## Démarrage / Arrêt / Logs

### Démarrer

```bash
sudo systemctl start neogrip.service
```

### Activer au boot
```bash
sudo systemctl enable neogrip.service
```

### Voir l'état
```bash
sudo systemctl status neogrip.service
```

### Logs temps réel
```bash
sudo journalctl -u neogrip.service -f
```

### Mode simulation (sans PCA9685 / sans I2C)

Ajouter la variable `NEOGRIP_DEV=1` pour forcer le backend simulé :

```bash
sudo nano /etc/neogrip/secrets.env
# Ajoutez :
NEOGRIP_DEV=1
```

puis effectué :

```bash
sudo systemctl restart neogrip.service
sudo journalctl -u neogrip.service -f
```
> Vous devriez voir des logs du type [DEV] ch=... pulse=....


## Erreurs récurrentes

### Cortex / Connectivité (erreur "connection refused")
Si vous voyez une erreur du type :
> Connect call failed ('127.0.0.1', 6868)

Alors Cortex n'écoute pas sur `localhost:6868`(ou n'est pas démarré)

### Dépannage matériel (I2C / Blinka / LGPIO)

#### PCA9685 non détecté
```bash
sudo i2cdetect -y 1
```

L'addresse du PCA9685 devrait remonter.

#### Erreurs LGPIO ("can not open gpiochip")

Vérifier que l'utilisateur du service (`eegsvc`) à bien accès à `gpio`:

```bash
id eegsvc
sudo usermod -aG gpio,i2c eegsvc
sudo systemctl restart neogrip.service
```

## Connection du casque à EMOTIV

Pour effectuer la connection du casque à la prothèse, il est impératif de suivre ces étapes :
1. Allumer le casque.
2. Aller sur l'application `EMOTIV Launcher`.
3. Connecter le casque à l'application.
4. Une fois le casque connecté, la prothèse commencera à recevoir les données.
5. Il est recommandé pour améliorer la précision de la prothèse d'effectuer des entraînements pour enrichir le profil utilisateur.
6. Les entraînement peuvent être effectué depuis l'application `EMOTIV BCI`. Les mouvement à entrainer sont :
    - Le `pull` il permet de fermer la main
    - Le `push` il permet d'ouvrir la main 

