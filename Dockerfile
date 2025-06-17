# Use a imagem oficial do Python como base
FROM python:3.9-slim-bullseye

# Define variáveis de ambiente
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive

# Instala dependências do sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libssl-dev \
    libffi-dev \
    python3-dev \
    sudo \
    wget \
    gnupg \
    lsb-release \
    apt-transport-https \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Instala o ttyd a partir do GitHub Releases
RUN wget -O /tmp/ttyd https://github.com/tsl0922/ttyd/releases/download/1.7.7/ttyd.x86_64 \
    && chmod +x /tmp/ttyd \
    && mv /tmp/ttyd /usr/local/bin/

# Adiciona repositório do LXD (versão estável)
RUN echo "deb https://ppa.launchpadcontent.net/ubuntu-lxc/lxd-stable/ubuntu focal main" > /etc/apt/sources.list.d/lxd-stable.list \
    && apt-key adv --keyserver keyserver.ubuntu.com --recv-keys 7635B973B6183192 \
    && apt-get update

# Instala LXD e dependências
RUN apt-get install -y --no-install-recommends \
    lxd \
    lxd-client \
    uidmap \
    && rm -rf /var/lib/apt/lists/*

# Configuração do LXD para usuário não-root
RUN echo "root:1000000:65536" >> /etc/subuid \
    && echo "root:1000000:65536" >> /etc/subgid

# Cria um usuário não-root para segurança
RUN useradd -m -u 1000 appuser && \
    usermod -aG lxd appuser && \
    echo "appuser ALL=(ALL) NOPASSWD: /usr/bin/lxc" >> /etc/sudoers

# Configura o diretório de trabalho
WORKDIR /app

# Copia os arquivos de requisitos primeiro para aproveitar o cache do Docker
COPY requirements.txt .

# Instala as dependências do Python
RUN pip install --no-cache-dir -r requirements.txt

# Copia o restante dos arquivos da aplicação
COPY . .

# Configura permissões
RUN chown -R appuser:appuser /app && \
    chmod +x /app/entrypoint.sh

# Muda para o usuário appuser
USER appuser

# Configura o LXD para o usuário (modo não-interativo)
RUN lxd init --auto

# Expõe as portas necessárias
EXPOSE 5000 

# ttyd
EXPOSE 7681

# Ponto de entrada
ENTRYPOINT ["/app/entrypoint.sh"]