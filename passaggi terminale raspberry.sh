# abilita l'autologin (System Options -> Auto Login -> Console Autologin)
# abilita VNC e SPI (Interface Options -> Enable VNC and SPI)
# abilita linguaggio Italiano (104 con tastiera con invio a forma di L )
sudo raspi-config

scp C:\xampp\htdocs\raspberryprojects\setup.zip pi@192.168.0.97:/home/pi/setup.zip

unzip setup.zip && cd setup && chmod +x setup.sh && ./setup.sh "RP1"
unzip setup.zip && cd setup && chmod +x setup.sh && ./setup.sh "RP1" 270
unzip setup.zip && cd setup && chmod +x setup_server.sh && ./setup_server.sh




ROTAZIONE_DYSPLAY="0"
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
sudo sed -i "s|__ROTATION__|$ROTAZIONE|g" /etc/systemd/system/chromium-kiosk.service
sudo sed -i "s|__TRANSFORMATION__|$MATRICE|g" /etc/systemd/system/chromium-kiosk.service
sudo systemctl stop chromium-kiosk.service
sudo systemctl daemon-reload
sudo systemctl disable chromium-kiosk.service
sudo systemctl enable chromium-kiosk.service
sudo systemctl start chromium-kiosk.service
sudo systemctl restart chromium-kiosk.service
sudo systemctl status chromium-kiosk.service

sudo systemctl stop flask.service
sudo systemctl daemon-reload
sudo systemctl disable flask.service
sudo systemctl enable flask.service
sudo systemctl start flask.service
sudo systemctl restart flask.service
sudo systemctl status flask.service
python /var/www/html/raspberryprojects/python/flask_project/manage.py
python /home/pi/flask_project/manage.py

# Secure installation of MySQL...
sudo mysql_secure_installation
# Riavvia apache
sudo service apache2 restart
# rimuovi chiave
ssh-keygen -R 192.168.0.150

pip freeze > requirements.txt

sudo systemctl stop flask.service
cd /var/www/html/raspberryprojects/python/flask_project
source venv/bin/activate
/var/www/html/raspberryprojects/python/flask_project/venv/bin/gunicorn --workers 1 --threads 8 --timeout 60 --bind 0.0.0.0:5000 manage:app

sudo systemctl stop flask.service
cd /home/webserver/flask_project
source venv/bin/activate
/home/webserver/flask_project/venv/bin/gunicorn --workers 1 --threads 8 --timeout 60 --bind 0.0.0.0:5000 manage:app

sudo systemctl stop flask.service
cd /home/pi/flask_project
source venv/bin/activate
/home/pi/flask_project/venv/bin/gunicorn --workers 1 --threads 8 --timeout 60 --bind 0.0.0.0:5000 manage:app

# se websocket non funziona
pkill -f "python"

stduser
PwD01NiVa18


chmod +x install.sh && chmod +x uninstall.sh && chmod +x test.sh


sudo nano /etc/systemd/system/plymouth-wait-for-animation.service
sudo nano /usr/share/plymouth/themes/niva/niva.plymouth
sudo nano /etc/plymouth/plymouthd.conf


sudo systemctl daemon-reload
sudo update-initramfs -u

sudo systemctl enable plymouth-wait-for-animation.service
sudo systemctl start plymouth-wait-for-animation.service
sudo nano /etc/plymouth/plymouthd.conf
sudo apt-get install plymouth plymouth-themes


sudo ./set_ip.sh eth0 192.168.0.100 24 192.168.0.253 8.8.8.8
sudo ./set_ip.sh wlan0 192.168.1.100 24 192.168.0.253 8.8.8.8 Niva_Office
