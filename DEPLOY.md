## Деплой бота на сервере

Протестировано на Debian 10.

Обновляем систему

```bash
sudo apt update && sudo apt upgrade
```

Устанавливаем Python 3.11 сборкой из исходников и sqlite3:

```bash
cd
sudo apt install -y sqlite3 pkg-config
wget https://www.python.org/ftp/python/3.11.1/Python-3.11.1.tgz
tar -xzvf Python-3.11.1.tgz
cd Python-3.11.1
./configure --enable-optimizations --prefix=/home/www/.python3.11
sudo make altinstall
```

Устанавливаем Poetry:

```basj
curl -sSL https://install.python-poetry.org | python3 -
```

Клонируем репозиторий в `~/code/wb_api_service`:

```bash
mkdir -p ~/code/
cd ~/code
git clone https://github.com/.../.git
cd wb_api_service
```

Создаём переменные окружения:

```
cp wb_api_service/.env.example wb_api_service/.env
vim wb_api_service/.env
```

`TELEGRAM_BOT_TOKEN` — токен бота, полученный в BotFather

Устанавливаем зависимости Poetry и запускаем бота вручную:

```bash
poetry install
poetry run python main.py
```

Можно проверить работу сервиса. Для остановки, жмём `CTRL`+`C`.

Получим текущий адрес до Pytnon-интерпретатора в poetry виртуальном окружении Poetry:

```bash
poetry shell which python
```
Скопируем путь до интерпретатора Python в виртуальном окружении.

Настроим systemd-юнит для автоматического запуска сервиса, подставив скопированный путь в ExecStart, а также убедившись,
что директория до проекта (в данном случае `/home/www/code/wb_api_service`) у вас такая же:

```
sudo tee /etc/systemd/system/wb_api_service.service << END
[Unit]
Description=Service for working with API Wildberries
After=network.target

[Service]
User=www
Group=www-data
WorkingDirectory=~/code/wb_api_service
Restart=on-failure
RestartSec=2s
ExecStart=/root/.cache/pypoetry/virtualenvs/wb_api_service-niaf6P17-py3.12/bin/python main.py

[Install]
WantedBy=multi-user.target
END

sudo systemctl daemon-reload
sudo systemctl enable wb_api_service.service
sudo systemctl start wb_api_service.service
```
