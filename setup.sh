#!/bin/bash

APP_NAME=$1
ROTAZIONE_DYSPLAY=$2
SCRIPT_DIR=$(dirname "$(realpath "$0")")
PROJECT_DIR="/var/www/html/raspberryprojects"
FLASK_DIR="$PROJECT_DIR/python/flask_project"
MIGRATIONS_DIR="$FLASK_DIR/migrations/versions"
DATABASE_NAME="IndustrySyncDB"

if [ -z "$ROTAZIONE_DYSPLAY" ]; then
    ROTAZIONE_DYSPLAY="0"
fi
case "$ROTAZIONE_DYSPLAY" in
    "0") echo "Nessuna rotazione applicata (default)." ;;
    "90") echo "Ruotando lo schermo di 90 gradi in senso orario." ;;
    "180") echo "Ruotando lo schermo di 180 gradi." ;;
    "270") echo "Ruotando lo schermo di 270 gradi in senso orario." ;;
    *) echo "Opzione di rotazione non valida: $ROTAZIONE_DYSPLAY. Usa 0, 90, 180, o 270." && exit 1 ;;
esac

echo "Aggiornamento della lista dei pacchetti in corso..." && sudo apt update -y >/dev/null 2>&1
echo "Aggiornamento dei pacchetti in corso..." && sudo apt upgrade -y >/dev/null 2>&1
echo "Aggiornamento del firmware Raspberry Pi in corso..." && sudo rpi-update -y >/dev/null 2>&1

echo "Installazione delle dipendenze in corso..."
sudo apt install -y --no-install-recommends xorg xserver-xorg-input-evdev xserver-xorg-input-libinput xinput-calibrator openbox chromium-browser git apache2 mariadb-server npm python3-pip python3-dev build-essential network-manager plymouth plymouth-themes vsftpd xinput arandr uuid-runtime libgpiod-dev python3-libgpiod python3-lgpio >/dev/null 2>&1
echo "Installazione completata!"

echo "Backup dei file di configurazione in corso..."
sudo cp /boot/cmdline.txt /boot/cmdline.txt.bak
sudo cp /boot/config.txt /boot/config.txt.bak
sudo cp /boot/firmware/cmdline.txt /boot/firmware/cmdline.txt.bak
sudo cp /boot/firmware/config.txt /boot/firmware/config.txt.bak
sudo cp /etc/vsftpd.conf /etc/vsftpd.conf.bak

echo "Configurazione cmdline.txt in corso..."
case "$ROTAZIONE_DYSPLAY" in
    "90")
        ROTAZIONE="right"
        MATRICE="0 -1 1 1 0 0 0 0 1"
        sudo sed -i "$ s/$/ fbcon=rotate:1/" /boot/firmware/cmdline.txt ;;
    "180")
        ROTAZIONE="normal"
        MATRICE="-1 0 1 0 -1 1 0 0 1"
        sudo sed -i "$ s/$/ fbcon=rotate:2/" /boot/firmware/cmdline.txt ;;
    "270")
        ROTAZIONE="left"
        MATRICE="0 1 0 -1 0 1 0 0 1"
        sudo sed -i "$ s/$/ fbcon=rotate:3/" /boot/firmware/cmdline.txt ;;
    *)
        ROTAZIONE="normal"
        MATRICE="1 0 0 0 1 0 0 0 1"
        sudo sed -i "$ s/$/ fbcon=rotate:0/" /boot/firmware/cmdline.txt ;;
esac
sudo sed -i "$ s/$/ video=DSI-1:800x480@60/" /boot/firmware/cmdline.txt
sudo sed -i "$ s/$/ rotate=$ROTAZIONE_DYSPLAY/" /boot/firmware/cmdline.txt
sudo sed -i "$ s/$/ splash/" /boot/firmware/cmdline.txt
sudo sed -i "$ s/$/ quiet/" /boot/firmware/cmdline.txt
sudo sed -i "$ s/$/ plymouth.ignore-serial-consoles/" /boot/firmware/cmdline.txt
sudo sed -i "$ s/$/ logo.nologo/" /boot/firmware/cmdline.txt
sudo sed -i "$ s/$/ vt.global_cursor_default=0/" /boot/firmware/cmdline.txt
sudo sed -i "$ s/$/ loglevel=0/" /boot/firmware/cmdline.txt
sudo sed -i "$ s/$/ elevator=deadline/" /boot/firmware/cmdline.txt
sudo sed -i "$ s/$/ dwc_otg.lpm_enable=0/" /boot/firmware/cmdline.txt
# if [ "$ROTAZIONE_DYSPLAY" == "0" ]; then
#     sudo sed -i "$ s/$/ boot=silent/" /boot/firmware/cmdline.txt
# fi

echo "Configurazione config.txt in corso..."
# sudo sed -i '/^\[all\]/a # Configurazione dello schermo HDMI-1' /boot/firmware/config.txt
# sudo sed -i '/^\[all\]/a hdmi_group=2' /boot/firmware/config.txt
# sudo sed -i '/^\[all\]/a hdmi_mode=87' /boot/firmware/config.txt
# sudo sed -i '/^\[all\]/a hdmi_cvt=800 480 66 1 0 0 0' /boot/firmware/config.txt
sudo sed -i '/^\[all\]/a disable_touchscreen=0' /boot/firmware/config.txt
sudo sed -i '/^\[all\]/a disable_splash=1' /boot/firmware/config.txt
sudo sed -i '/^\[all\]/a dtparam=i2c_arm=on' /boot/firmware/config.txt
sudo sed -i '/^\[all\]/a dtparam=spi=on' /boot/firmware/config.txt
sudo sed -i '/^\[all\]/a enable_dpi_lcd=1' /boot/firmware/config.txt
sudo sed -i '/^\[all\]/a display_default_lcd=1' /boot/firmware/config.txt
sudo sed -i '/^\[all\]/a dpi_group=2' /boot/firmware/config.txt
sudo sed -i '/^\[all\]/a dpi_mode=87' /boot/firmware/config.txt
sudo sed -i '/^\[all\]/a dpi_output_format=0x7f216' /boot/firmware/config.txt
sudo sed -i '/^\[all\]/a hdmi_timings=800 0 40 40 40 480 0 13 29 3 0 0 0 60 0 32000000 6' /boot/firmware/config.txt
sudo sed -i '/^\[all\]/a video=DSI-1:800x480@60' /boot/firmware/config.txt

# sudo cp -a "$SCRIPT_DIR/os_sync/." /
# sudo rsync -a --ignore-existing "$SCRIPT_DIR/os_sync/." /
# sudo rsync -a --inplace "$SCRIPT_DIR/os_sync/." /
# sudo rsync -a "$SCRIPT_DIR/os_sync/." /
echo "Copia dei file di sincronizzazione in corso..."
sudo rsync -a --no-perms --no-owner --no-group --inplace "$SCRIPT_DIR/os_sync/." /

echo "Sostituzione dei parametri in corso..."
sudo sed -i "s/^\(transform *= *\).*/\1$(if [ "$ROTAZIONE_DYSPLAY" == "0" ]; then echo 'normal'; else echo "$ROTAZIONE_DYSPLAY"; fi)/" /home/pi/.config/wayfire.ini
sudo sed -i "s|__PATH__|$FLASK_DIR|g" /etc/systemd/system/flask.service
sudo sed -i "s|__ROTATION__|$ROTAZIONE|g" /etc/systemd/system/chromium-kiosk.service
sudo sed -i "s|__TRANSFORMATION__|$MATRICE|g" /etc/systemd/system/chromium-kiosk.service
# sudo sed -i "s|logoniva|logoniva$ROTAZIONE_DYSPLAY|g" /usr/share/plymouth/themes/niva/niva.script

echo "Reimpostazione dei permessi in corso..."
sudo chown -R pi:pi /home/pi/.config
sudo chown -R root:root /etc/systemd/system
sudo chown -R root:root /usr/share/plymouth/themes/niva

echo "Creazione del database in corso..."
sudo mysql -u root -praspberry -e "
DROP USER IF EXISTS 'niva'@'%';
CREATE USER 'niva'@'%' IDENTIFIED BY '01NiVa18';
DROP DATABASE IF EXISTS $DATABASE_NAME;
CREATE DATABASE IF NOT EXISTS $DATABASE_NAME;
GRANT ALL PRIVILEGES ON *.* TO 'niva'@'%' WITH GRANT OPTION;
FLUSH PRIVILEGES;
"

echo "Modifica dei file in corso..."
sudo sh -c 'echo -n > /etc/motd'
sudo sh -c 'echo -n > /etc/issue'
sudo sh -c 'echo -n > /etc/issue.net'
sudo sed -i 's/^/#/' /etc/pam.d/login
sudo sed -i 's/^/#/' /etc/profile.d/sshpwd.sh
sudo mv /etc/issue.d/IP.issue /etc/issue.d/IP.issue.bak
echo '[[ -z $DISPLAY && $XDG_VTNR -eq 1 ]] && exec startx -- -nocursor -quiet > /dev/null 2>&1' >> "$HOME/.profile"
sudo sed -i '/ExecStart=-\/sbin\/agetty -o .* --noclear - \$TERM/s/^/# /; /# ExecStart=-\/sbin\/agetty -o .* --noclear - \$TERM/a ExecStart=-/sbin/agetty --noclear %I $TERM' /lib/systemd/system/getty@.service
echo "mesg n" >> "$HOME/.bashrc"
echo "127.0.0.1       raspberryprojects.local" | sudo tee -a /etc/hosts >/dev/null 2>&1
echo "[mysqld]" | sudo tee -a /etc/mysql/my.cnf >/dev/null 2>&1
echo "bind-address = 0.0.0.0" | sudo tee -a /etc/mysql/my.cnf >/dev/null 2>&1

echo "Riavvio di Apache..."
sudo a2enmod rewrite >/dev/null 2>&1
sudo a2ensite raspberryprojects.conf >/dev/null 2>&1
sudo systemctl restart apache2 >/dev/null 2>&1
echo "Riavvio di MySQL..."
sudo systemctl restart mysql

echo "Installazione PHP 8..."
sudo wget -qO /etc/apt/trusted.gpg.d/php.gpg https://packages.sury.org/php/apt.gpg >/dev/null 2>&1
echo "deb https://packages.sury.org/php/ $(lsb_release -sc) main" | sudo tee /etc/apt/sources.list.d/php.list >/dev/null
sudo apt update -y >/dev/null 2>&1
sudo apt install -y php8.1-common php8.1-cli php8.1-curl php8.1-gd php8.1-mbstring php8.1-xml php8.1-zip php8.1-mysql libapache2-mod-php8.1 >/dev/null 2>&1
sudo service apache2 restart >/dev/null 2>&1

echo "Installazione Composer..."
sudo wget -qO composer-setup.php https://getcomposer.org/installer >/dev/null 2>&1
sudo php composer-setup.php --install-dir=/usr/local/bin --filename=composer >/dev/null 2>&1
composer --version >/dev/null 2>&1
sudo rm -rf composer-setup.php
sudo composer self-update >/dev/null 2>&1

echo "Installazione Laravel - Clonando raspberryprojects..."
cd /var/www/html
sudo git clone https://github.com/riccardopanico/raspberryprojects.git >/dev/null 2>&1
sudo chown -R pi:www-data "$PROJECT_DIR"
sudo chmod -R 775 "$PROJECT_DIR"

echo "Installazione dipendenze laravel..."
cd "$PROJECT_DIR"
sudo COMPOSER_ALLOW_SUPERUSER=1 composer install >/dev/null 2>&1
sudo npm install >/dev/null 2>&1
sudo npm run dev >/dev/null 2>&1

echo "Creazione .env..."
ENV_FILE="$PROJECT_DIR/.env"
sudo cp "$SCRIPT_DIR/.env_laravel" "$ENV_FILE"
sudo sed -i "s/^APP_NAME=.*/APP_NAME=$APP_NAME/" "$ENV_FILE"
sudo sed -i "s/^DB_CONNECTION=.*/DB_CONNECTION=mysql/" "$ENV_FILE"
sudo sed -i "s/^DB_HOST=.*/DB_HOST=localhost/" "$ENV_FILE"
sudo sed -i "s/^DB_PORT=.*/DB_PORT=3306/" "$ENV_FILE"
sudo sed -i "s/^DB_DATABASE=.*/DB_DATABASE=$DATABASE_NAME/" "$ENV_FILE"
sudo sed -i "s/^DB_USERNAME=.*/DB_USERNAME=niva/" "$ENV_FILE"
sudo sed -i "s/^DB_PASSWORD=.*/DB_PASSWORD=01NiVa18/" "$ENV_FILE"

echo "Clonazione del progetto Flask..."
cd "$PROJECT_DIR"
sudo mkdir python
sudo chown -R pi:www-data "$PROJECT_DIR/python"
sudo chmod -R 775 "$PROJECT_DIR/python"
cd "$PROJECT_DIR/python"
sudo git clone --branch device https://github.com/riccardopanico/flask_project.git "$FLASK_DIR" >/dev/null 2>&1
sudo cp "$SCRIPT_DIR/.env_flask" "$FLASK_DIR/.env"
sudo chown -R pi:www-data "$PROJECT_DIR/python"
sudo chmod -R 775 "$PROJECT_DIR/python"

echo "Configurazione del virtual environment per il progetto Flask..."
cd "$FLASK_DIR"
python3 -m venv venv
source "$FLASK_DIR/venv/bin/activate"
pip install -r "$FLASK_DIR/requirements.txt" >/dev/null 2>&1
sudo rm -rf "$FLASK_DIR/migrations/"
flask db init >/dev/null 2>&1
flask db migrate -m "Migrazioni generate dai modelli" >/dev/null 2>&1
flask db upgrade >/dev/null 2>&1
echo "Copia e processamento delle migrazioni personalizzate..."
PREVIOUS_REVISION=$(flask db heads | grep -oE "^[a-f0-9]{12}")
mkdir -p "$MIGRATIONS_DIR"
for file in $(ls "$SCRIPT_DIR/migrations/versions/"*.py | sort); do
    NEW_REVISION=$(uuidgen | tr -d '-' | tr '[:upper:]' '[:lower:]' | head -c 12)
    BASENAME=$(basename "$file" .py)
    TARGET_FILE="$MIGRATIONS_DIR/${NEW_REVISION}_$(echo "$BASENAME" | tr ' ' '_').py"
    cp "$file" "$TARGET_FILE"
    sed -i "s/^revision = None/revision = '$NEW_REVISION'/g" "$TARGET_FILE"
    sed -i "s/^down_revision = None/down_revision = '$PREVIOUS_REVISION'/g" "$TARGET_FILE"
    echo "Migrazione personalizzata processata: $TARGET_FILE"
    PREVIOUS_REVISION=$NEW_REVISION
done
flask db upgrade >/dev/null 2>&1
deactivate

echo Installazione del tema niva...
sudo update-alternatives --quiet --install /usr/share/plymouth/themes/default.plymouth default.plymouth "/usr/share/plymouth/themes/niva_$ROTAZIONE_DYSPLAY/niva_$ROTAZIONE_DYSPLAY.plymouth" 100  >/dev/null 2>&1
sudo update-alternatives --quiet --set default.plymouth "/usr/share/plymouth/themes/niva_$ROTAZIONE_DYSPLAY/niva_$ROTAZIONE_DYSPLAY.plymouth"  >/dev/null 2>&1
sudo update-initramfs -u  >/dev/null 2>&1
# sudo plymouthd && sudo plymouth --show-splash && sleep 7 && sudo plymouth quit
# sudo plymouthd && sudo plymouth --show-splash && sleep 7 && sudo plymouth deactivate && sudo plymouth quit

# sudo plymouth-set-default-theme -R niva --rebuild-initrd >/dev/null 2>&1
# sudo update-initramfs -u >/dev/null 2>&1

echo "Riavvio dei servizi..."
sudo systemctl daemon-reload >/dev/null 2>&1
sudo systemctl restart vsftpd >/dev/null 2>&1
sudo systemctl enable plymouth-wait-for-animation.service >/dev/null 2>&1

echo "
#######  ###  #     #  #######
#         #   ##    #  #
#         #   # #   #  #
#####     #   #  #  #  #####
#         #   #   # #  #
#         #   #    ##  #
#        ###  #     #  #######
"

sudo reboot
