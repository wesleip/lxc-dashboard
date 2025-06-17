import os
import time
import threading
import subprocess
from datetime import datetime
from io import BytesIO
import base64
import socket

import psutil
import matplotlib.pyplot as plt
from flask import Flask, render_template, request, redirect, url_for, jsonify, flash
from flask_socketio import SocketIO, emit
from pylxd import Client
from pylxd.exceptions import LXDAPIException

# Inicialização da aplicação
app = Flask(__name__)
app.secret_key = os.urandom(24)
socketio = SocketIO(app)

# Variáveis globais
ttyd_processes = {}

class LXDManager:
    @staticmethod
    def get_client():
        """Retorna um cliente LXD configurado"""
        return Client()

    @staticmethod
    def get_container_ip(container):
        """Obtém o endereço IP principal de um container"""
        try:
            state = container.state()
            if state and state.network:
                for interface_name, interface in state.network.items():
                    for address in interface['addresses']:
                        if address['family'] == 'inet' and address['scope'] == 'global':
                            return address['address']
        except Exception:
            pass
        return 'N/A'

    @staticmethod
    def get_container_stats(container_name, stat_type):
        """Obtém estatísticas do container (CPU ou memória)"""
        try:
            client = LXDManager.get_client()
            container = client.containers.get(container_name)
            state = container.state()
            
            if not state:
                return 'N/A'
            
            if stat_type == 'cpu':
                return f"{state.cpu['usage']}%"
            elif stat_type == 'memory':
                mem_usage = state.memory['usage'] / (1024 * 1024)
                return f"{mem_usage:.2f} MB"
        except Exception:
            return 'N/A'

    @staticmethod
    def generate_plots(container_name):
        """Gera gráficos de CPU e memória para o container"""
        # Simulação de coleta de dados (substituir por dados reais em produção)
        timestamps = []
        cpu_usage = []
        mem_usage = []
        
        for i in range(10):
            timestamps.append(datetime.now().strftime('%H:%M:%S'))
            cpu_usage.append(psutil.cpu_percent())
            mem_usage.append(psutil.virtual_memory().percent)
            time.sleep(1)
        
        # Gráfico de CPU
        plt.figure(figsize=(10, 4))
        plt.plot(timestamps, cpu_usage, marker='o')
        plt.title(f'Uso de CPU - {container_name}')
        plt.xlabel('Tempo')
        plt.ylabel('Uso (%)')
        plt.grid(True)
        cpu_buffer = BytesIO()
        plt.savefig(cpu_buffer, format='png')
        cpu_buffer.seek(0)
        plt.close()
        
        # Gráfico de memória
        plt.figure(figsize=(10, 4))
        plt.plot(timestamps, mem_usage, marker='o', color='orange')
        plt.title(f'Uso de Memória - {container_name}')
        plt.xlabel('Tempo')
        plt.ylabel('Uso (%)')
        plt.grid(True)
        mem_buffer = BytesIO()
        plt.savefig(mem_buffer, format='png')
        mem_buffer.seek(0)
        plt.close()
        
        return (
            base64.b64encode(cpu_buffer.getvalue()).decode('utf-8'),
            base64.b64encode(mem_buffer.getvalue()).decode('utf-8')
        )

class TerminalManager:
    @staticmethod
    def find_free_port():
        """Encontra uma porta TCP disponível"""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('0.0.0.0', 0))
            return s.getsockname()[1]

    @staticmethod
    def start_terminal(container_name):
        """Inicia um terminal web para o container especificado"""
        try:
            if container_name in ttyd_processes:
                return {'status': 'already running', 'port': ttyd_processes[container_name]['port']}
            
            port = TerminalManager.find_free_port()
            cmd = f"ttyd -p {port} lxc exec {container_name} -- /bin/bash"
            process = subprocess.Popen(cmd, shell=True)
            
            ttyd_processes[container_name] = {
                'process': process,
                'port': port
            }
            
            return {'status': 'started', 'port': port}
        except Exception as e:
            raise RuntimeError(f"Failed to start terminal: {str(e)}")

    @staticmethod
    def stop_terminal(container_name):
        """Para o terminal web do container especificado"""
        try:
            if container_name in ttyd_processes:
                ttyd_processes[container_name]['process'].terminate()
                del ttyd_processes[container_name]
                return {'status': 'stopped'}
            return {'status': 'not running'}
        except Exception as e:
            raise RuntimeError(f"Failed to stop terminal: {str(e)}")

# Rotas da aplicação
@app.route('/')
def index():
    """Página principal com lista de containers"""
    try:
        client = LXDManager.get_client()
        containers = client.containers.all()
        images = client.images.all()
        
        containers_info = []
        for container in containers:
            state = container.state()
            containers_info.append({
                'name': container.name,
                'status': container.status,
                'state': state.status if state else 'unknown',
                'ipv4': LXDManager.get_container_ip(container),
                'architecture': container.architecture,
                'created_at': container.created_at,
                'cpu_usage': LXDManager.get_container_stats(container.name, 'cpu'),
                'memory_usage': LXDManager.get_container_stats(container.name, 'memory')
            })
        
        return render_template('index.html', 
                            containers=containers_info,
                            images=images)
    except LXDAPIException as e:
        flash(f"Erro ao conectar ao LXD: {str(e)}", 'danger')
        return render_template('index.html', containers=[], images=[])

@app.route('/container/<action>/<name>')
def container_action(action, name):
    """Executa ações básicas nos containers (start, stop, restart, delete)"""
    try:
        client = LXDManager.get_client()
        container = client.containers.get(name)
        
        if action == 'start' and container.status == 'Stopped':
            container.start(wait=True)
            flash(f'Container {name} iniciado com sucesso', 'success')
        elif action == 'stop' and container.status == 'Running':
            TerminalManager.stop_terminal(name)
            container.stop(wait=True)
            flash(f'Container {name} parado com sucesso', 'success')
        elif action == 'restart' and container.status == 'Running':
            container.restart(wait=True)
            flash(f'Container {name} reiniciado com sucesso', 'success')
        elif action == 'delete':
            TerminalManager.stop_terminal(name)
            if container.status == 'Running':
                container.stop(wait=True)
            container.delete(wait=True)
            flash(f'Container {name} removido com sucesso', 'success')
        else:
            flash(f'Ação não permitida no estado atual do container', 'warning')
    except LXDAPIException as e:
        flash(f'Erro ao executar ação no container: {str(e)}', 'danger')
    
    return redirect(url_for('index'))

@app.route('/create', methods=['GET', 'POST'])
def create_container():
    """Cria um novo container LXD"""
    if request.method == 'POST':
        try:
            client = LXDManager.get_client()
            config = {
                'name': request.form['name'],
                'source': {'type': 'image', 'alias': request.form['image']},
                'profiles': [request.form.get('profile', 'default')]
            }
            
            container = client.containers.create(config, wait=True)
            
            if request.form.get('start_after_create') == 'on':
                container.start(wait=True)
                flash(f'Container {container.name} criado e iniciado com sucesso', 'success')
            else:
                flash(f'Container {container.name} criado com sucesso', 'success')
            
            return redirect(url_for('index'))
        except LXDAPIException as e:
            flash(f'Erro ao criar container: {str(e)}', 'danger')
            return redirect(url_for('create_container'))
    
    # GET request
    try:
        client = LXDManager.get_client()
        return render_template('create.html',
                            images=client.images.all(),
                            profiles=client.profiles.all())
    except LXDAPIException as e:
        flash(f'Erro ao obter lista de imagens/perfis: {str(e)}', 'danger')
        return redirect(url_for('index'))

@app.route('/logs/<container_name>')
def view_logs(container_name):
    """Exibe logs do container"""
    try:
        client = LXDManager.get_client()
        container = client.containers.get(container_name)
        logs = container.execute(['cat', '/var/log/syslog'])
        return render_template('logs.html',
                            container_name=container_name,
                            logs=logs.stdout)
    except LXDAPIException as e:
        flash(f'Erro ao obter logs: {str(e)}', 'danger')
        return redirect(url_for('index'))

@app.route('/metrics/<container_name>')
def view_metrics(container_name):
    """Exibe métricas de desempenho do container"""
    try:
        cpu_plot, memory_plot = LXDManager.generate_plots(container_name)
        return render_template('metrics.html',
                            container_name=container_name,
                            cpu_plot=cpu_plot,
                            memory_plot=memory_plot)
    except Exception as e:
        flash(f'Erro ao gerar métricas: {str(e)}', 'danger')
        return redirect(url_for('index'))

@app.route('/console/<container_name>')
def console(container_name):
    """Página do terminal web"""
    try:
        # Verifica se o terminal já está rodando ou inicia um novo
        if container_name in ttyd_processes:
            port = ttyd_processes[container_name]['port']
        else:
            result = TerminalManager.start_terminal(container_name)
            port = result['port']
        
        return render_template('console.html', 
                           container_name=container_name,
                           port=port)
    except Exception as e:
        flash(f'Erro ao acessar terminal: {str(e)}', 'danger')
        return redirect(url_for('index'))

@app.route('/start_terminal/<container_name>')
def start_terminal(container_name):
    """API para iniciar terminal web"""
    try:
        result = TerminalManager.start_terminal(container_name)
        return jsonify(result)
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/stop_terminal/<container_name>')
def stop_terminal(container_name):
    """API para parar terminal web"""
    try:
        result = TerminalManager.stop_terminal(container_name)
        return jsonify(result)
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

# Context processors e inicialização
@app.context_processor
def inject_now():
    """Injeta a data atual nos templates"""
    return {'now': datetime.now()}

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)