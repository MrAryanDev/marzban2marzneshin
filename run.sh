# set MAIN_DIR = /opt/MrAryanDev
export MAIN_DIR="/opt/MrAryanDev"

# set clone folder = "cloned"
export CLONE_FOLDER="cloned"

# set APP_NAME = marzban2marzneshin
export APP_NAME="marzban2marzneshin"

# set repository = https://github.com/MrAryanDev/marzban2marzneshin
export repository="https://github.com/MrAryanDev/marzban2marzneshin.git"

# set venv = /opt/MrAryanDev/.venv
export venv="${MAIN_DIR}/.venv"

# set python executable = /opt/MrAryanDev/.venv/bin/python
export python="${venv}/bin/python"

# set pip executable = /opt/MrAryanDev/.venv/bin/pip
export pip="${venv}/bin/pip"

sudo apt update -y && sudo apt upgrade -y
sudo apt install -y python3 python3-pip python3-venv unzip wget git

# check MAIN_DIR exists
if [ ! -d "$MAIN_DIR" ]; then
  mkdir -p "$MAIN_DIR"
fi

# check CLONE_FOLDER exists
if [ ! -d "$MAIN_DIR/$CLONE_FOLDER" ]; then
  mkdir -p "$MAIN_DIR/$CLONE_FOLDER"
fi

# check APP_NAME exists
if [ ! -d "$MAIN_DIR/$APP_NAME" ]; then
  mkdir -p "$MAIN_DIR/$APP_NAME"
fi

# go to clone folder
cd "$MAIN_DIR/$CLONE_FOLDER" || exit

# force clone repository
if [ -d "${MAIN_DIR:?}/$CLONE_FOLDER/$APP_NAME" ]; then
  rm -rf "${MAIN_DIR:?}/$CLONE_FOLDER/$APP_NAME"
fi
git clone "$repository"

# check venv exists
if [ ! -d "$venv" ]; then
  python3 -m venv "$venv"
fi

cd "$MAIN_DIR/$CLONE_FOLDER/$APP_NAME" || exit

# check requirements.txt exists
if [ ! -f "requirements.txt" ]; then
  echo "requirements.txt not found"
  exit 1
fi

# install requirements
"$pip" install -r requirements.txt

# run migrate.py
"$python" migrate-script/migrate.py




