#!/bin/bash

# Configura o LXD para aceitar conexões
lxc config set core.https_address "[::]"
lxc config set core.trust_password "lxdmanager"

# Inicia o ttyd em segundo plano
sudo /usr/local/bin/ttyd -p 7681 -c admin:password bash > /var/log/ttyd.log 2>&1 &

# Inicia a aplicação Flask
exec flask run --host=0.0.0.0 --port=5000