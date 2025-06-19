FROM python:3.9-slim-bullseye

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive

ARG LXD_GID=133

# Instala dependências de sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libssl-dev \
    libffi-dev \
    python3-dev \
    sudo \
    wget \
    curl \
    gnupg \
    ca-certificates \
    uidmap \
    lxc \
    jq \
    && rm -rf /var/lib/apt/lists/*

# Instala ttyd
RUN wget -O /tmp/ttyd https://github.com/tsl0922/ttyd/releases/download/1.7.7/ttyd.x86_64 \
    && chmod +x /tmp/ttyd \
    && mv /tmp/ttyd /usr/local/bin/

# Cria usuário não-root
RUN useradd -m -u 1000 appuser && \
    echo "appuser ALL=(ALL) NOPASSWD: /usr/bin/lxc" >> /etc/sudoers

# Diretório da aplicação
WORKDIR /app

# Instala Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia aplicação
COPY . .

# Permissões
RUN chown -R appuser:appuser /app && \
    chmod +x /app/entrypoint.sh

RUN groupadd -g ${LXD_GID} lxd && \
    usermod -aG lxd appuser
# Muda para o usuário
USER appuser

# Expõe portas (ajuste conforme necessário)
EXPOSE 5000
EXPOSE 7681

# Ponto de entrada
ENTRYPOINT ["/app/entrypoint.sh"]
