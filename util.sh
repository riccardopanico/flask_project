
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
bash Miniconda3-latest-Linux-x86_64.sh
conda init bash

git clone -b datacenter_new https://github.com/riccardopanico/flask_project.git flask_project_datacenter
cd ~/flask_project_datacenter
conda env create -f environment.yml
conda activate flask_project_datacenter


which gunicorn
/home/popos_ai2/miniconda3/envs/flask_project_datacenter/bin/gunicorn --workers 1 --threads 8 --timeout 60 --bind 0.0.0.0:5000 manage:app

rm -rf migrations/

DATABASE_NAME="IndustrySyncDB"

echo "Creazione del database in corso..."
sudo mysql -u root -praspberry -e "
DROP USER IF EXISTS 'niva'@'%';
CREATE USER 'niva'@'%' IDENTIFIED BY '01NiVa18';
DROP DATABASE IF EXISTS $DATABASE_NAME;
CREATE DATABASE IF NOT EXISTS $DATABASE_NAME;
GRANT ALL PRIVILEGES ON *.* TO 'niva'@'%' WITH GRANT OPTION;
FLUSH PRIVILEGES;
"

flask db init
flask db migrate -m "fix variable unique constraint"
flask db upgrade
