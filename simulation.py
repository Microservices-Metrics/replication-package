import subprocess
import sys
import shutil
import argparse
import json
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

parser = argparse.ArgumentParser(description="Script de preparação do ambiente e criação de métricas")
parser.add_argument(
    "--forcar-recriacao-ids",
    action="store_true",
    help="Força a recriação dos IDs (métricas e microserviços) e sobrescreve o arquivo de configuração.",
)
parser.add_argument(
    "--limpar-banco-dados",
    action="store_true",
    help="Limpa dados persistidos do banco antes da subida, executando 'docker compose down -v'.",
)
args = parser.parse_args()

# ==========================================
# VERIFICAÇÕES INICIAIS
# ==========================================
def verificar_dependencias():
    print("🔍 Verificando dependências...")
    if shutil.which("docker") is None:
        print("❌ ERRO: O Docker não está instalado ou não foi encontrado.")
        sys.exit(1)
    if shutil.which("git") is None:
        print("❌ ERRO: O Git não está instalado no sistema.")
        sys.exit(1)
    try:
        subprocess.run(["docker", "compose", "version"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except subprocess.CalledProcessError:
        print("❌ ERRO: O 'Docker Compose' não está disponível.")
        sys.exit(1)
    print("✅ Dependências ok!\n" + "="*40)

verificar_dependencias()

# ==========================================
# CONFIGURAÇÕES
# ==========================================
REPOSITORIOS = {
    "metrichub": [
        "https://github.com/Microservices-Metrics/metrics-manager",
        "https://github.com/Microservices-Metrics/metrics-front"
    ],
    "collectors": [
        "https://github.com/Microservices-Metrics/openapi-metric-collector",
        "https://github.com/Microservices-Metrics/code-metric-collector",
        "https://github.com/Microservices-Metrics/log-metric-collector",
        "https://github.com/Microservices-Metrics/code-db-connections-metric-collector",
        "https://github.com/Microservices-Metrics/log-db-conns-metric-collector",
    ],
    "microservices": [
        "https://github.com/brunopromano/amaris-contabil",
        "https://github.com/brunopromano/finance-users-api",
        "https://github.com/brunopromano/painel-contabil"
    ]
}

CHAVE_PARA_SECAO = {
    "idNumberofEndpointsMetric": "metrics",
    "idDatabaseConnectionsMetric": "metrics",
    "idAmarisContabilMicroservice": "microservices",
    "idFinanceUsersMicroservice": "microservices",
    "idPainelContabilMicroservice": "microservices",
    "idOpenApiEndpointsCollector": "collectors",
    "idSourceCodeCollector": "collectors",
    "idLogMetricOperationsCollector": "collectors",
    "idCodeDbConnectionsCollector": "collectors",
    "idDockerComposeDbConnsCollector": "collectors",
    "idLogDBMetricOperationsCollector": "collectors",
    "idOpenApiAmarisCollectorConfig": "collectorConfigs",
    "idOpenApiFinanceUsersCollectorConfig": "collectorConfigs",
    "idOpenApiPainelContabilCollectorConfig": "collectorConfigs",
    "idSourceCodeAmarisCollectorConfig": "collectorConfigs",
    "idSourceCodeFinanceUsersCollectorConfig": "collectorConfigs",
    "idSourceCodePainelContabilCollectorConfig": "collectorConfigs",
    "idLogMetricAmarisCollectorConfig": "collectorConfigs",
    "idLogMetricFinanceUsersCollectorConfig": "collectorConfigs",
    "idLogMetricPainelContabilCollectorConfig": "collectorConfigs",
    "idCodeDbAmarisCollectorConfig": "collectorConfigs",
    "idCodeDbFinanceUsersCollectorConfig": "collectorConfigs",
    "idCodeDbPainelContabilCollectorConfig": "collectorConfigs",
    "idDockerComposeAmarisCollectorConfig": "collectorConfigs",
    "idDockerComposeFinanceUsersCollectorConfig": "collectorConfigs",
    "idDockerComposePainelContabilCollectorConfig": "collectorConfigs",
    "idLogDBMetricAmarisCollectorConfig": "collectorConfigs",
    "idLogDBMetricFinanceUsersCollectorConfig": "collectorConfigs",
    "idLogDBMetricPainelContabilCollectorConfig": "collectorConfigs",
}

def run_command(command, cwd=None):
    """Executa um comando e lança um erro se falhar, permitindo capturar depois."""
    try:
        subprocess.run(command, cwd=cwd, check=True, text=True)
    except subprocess.CalledProcessError as e:
        print(f"❌ Erro ao executar: {' '.join(command)}")
        raise e  # Propaga o erro para o bloco principal tratar


def criar_metrica(payload):
    """Cria uma métrica na API e retorna o ID retornado pelo serviço."""
    data = json.dumps(payload).encode("utf-8")
    request_body = json.dumps(payload, ensure_ascii=False)
    endpoint = "http://localhost:8080/metrics"
    headers = {"Content-Type": "application/json"}

    print("-"*100)
    print("📨 Requisição HTTP")
    print(f"   Método: POST")
    print(f"   URL: {endpoint}")
    print(f"   Headers: {headers}")
    print(f"   Body: {request_body}")
    print("⏳ Enviando requisição para criar métrica...\n")

    req = urllib.request.Request(
        endpoint,
        data=data,
        headers=headers,
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            status_code = response.getcode()
            body = response.read().decode("utf-8")
            print("📥 Resposta HTTP")
            print(f"   Status: {status_code}")
            print(f"   Body: {body}")
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8", errors="ignore")
        print("📥 Resposta HTTP")
        print(f"   Status: {e.code}")
        print(f"   Body: {error_body}")
        print(f"❌ Erro HTTP ao criar métrica '{payload.get('name')}': {e.code} - {error_body}")
        raise
    except urllib.error.URLError as e:
        print(f"❌ Erro de conexão ao criar métrica '{payload.get('name')}': {e.reason}")
        raise

    try:
        response_json = json.loads(body) if body else {}
    except json.JSONDecodeError:
        print(f"❌ Resposta inválida ao criar métrica '{payload.get('name')}': {body}")
        raise

    metric_id = response_json.get("idMetric")
    
    if metric_id is None:
        print(f"❌ A resposta não contém um ID para a métrica '{payload.get('name')}': {response_json}")
        raise ValueError("ID da métrica não encontrado na resposta")

    return metric_id


def criar_microservico(payload):
    """Cria um microserviço na API e retorna o ID retornado no campo $.id."""
    data = json.dumps(payload).encode("utf-8")
    request_body = json.dumps(payload, ensure_ascii=False)
    endpoint = "http://localhost:8080/microservices"
    headers = {"Content-Type": "application/json"}

    print("-"*100)
    print("📨 Requisição HTTP")
    print("   Método: POST")
    print(f"   URL: {endpoint}")
    print(f"   Headers: {headers}")
    print(f"   Body: {request_body}")
    print("⏳ Enviando requisição para criar microserviço...\n")

    req = urllib.request.Request(
        endpoint,
        data=data,
        headers=headers,
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            status_code = response.getcode()
            body = response.read().decode("utf-8")
            print("📥 Resposta HTTP")
            print(f"   Status: {status_code}")
            print(f"   Body: {body}")
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8", errors="ignore")
        print("📥 Resposta HTTP")
        print(f"   Status: {e.code}")
        print(f"   Body: {error_body}")
        print(f"❌ Erro HTTP ao criar microserviço '{payload.get('name')}': {e.code} - {error_body}")
        raise
    except urllib.error.URLError as e:
        print(f"❌ Erro de conexão ao criar microserviço '{payload.get('name')}': {e.reason}")
        raise

    try:
        response_json = json.loads(body) if body else {}
    except json.JSONDecodeError:
        print(f"❌ Resposta inválida ao criar microserviço '{payload.get('name')}': {body}")
        raise

    microservice_id = response_json.get("id")
    if microservice_id is None:
        print(f"❌ A resposta não contém $.id para o microserviço '{payload.get('name')}': {response_json}")
        raise ValueError("ID do microserviço não encontrado na resposta")

    return microservice_id


def criar_collector(payload):
    """Cria um collector na API e retorna o ID retornado no campo $.id."""
    data = json.dumps(payload).encode("utf-8")
    request_body = json.dumps(payload, ensure_ascii=False)
    endpoint = "http://localhost:8080/collectors"
    headers = {"Content-Type": "application/json"}

    print("-"*100)
    print("📨 Requisição HTTP")
    print("   Método: POST")
    print(f"   URL: {endpoint}")
    print(f"   Headers: {headers}")
    print(f"   Body: {request_body}")
    print("⏳ Enviando requisição para criar collector...\n")

    req = urllib.request.Request(
        endpoint,
        data=data,
        headers=headers,
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            status_code = response.getcode()
            body = response.read().decode("utf-8")
            print("📥 Resposta HTTP")
            print(f"   Status: {status_code}")
            print(f"   Body: {body}")
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8", errors="ignore")
        print("📥 Resposta HTTP")
        print(f"   Status: {e.code}")
        print(f"   Body: {error_body}")
        print(f"❌ Erro HTTP ao criar collector '{payload.get('name')}': {e.code} - {error_body}")
        raise
    except urllib.error.URLError as e:
        print(f"❌ Erro de conexão ao criar collector '{payload.get('name')}': {e.reason}")
        raise

    try:
        response_json = json.loads(body) if body else {}
    except json.JSONDecodeError:
        print(f"❌ Resposta inválida ao criar collector '{payload.get('name')}': {body}")
        raise

    collector_id = response_json.get("id")
    if collector_id is None:
        print(f"❌ A resposta não contém $.id para o collector '{payload.get('name')}': {response_json}")
        raise ValueError("ID do collector não encontrado na resposta")

    return collector_id


def criar_collector_config(payload):
    """Cria uma configuração de coleta e retorna o ID em $.id."""
    data = json.dumps(payload).encode("utf-8")
    request_body = json.dumps(payload, ensure_ascii=False)
    endpoint = "http://localhost:8080/collector-configs"
    headers = {"Content-Type": "application/json"}

    print("-"*100)
    print("📨 Requisição HTTP")
    print("   Método: POST")
    print(f"   URL: {endpoint}")
    print(f"   Headers: {headers}")
    print(f"   Body: {request_body}")
    print("⏳ Enviando requisição para criar collector-config...\n")

    req = urllib.request.Request(
        endpoint,
        data=data,
        headers=headers,
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            status_code = response.getcode()
            body = response.read().decode("utf-8")
            print("📥 Resposta HTTP")
            print(f"   Status: {status_code}")
            print(f"   Body: {body}")
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8", errors="ignore")
        print("📥 Resposta HTTP")
        print(f"   Status: {e.code}")
        print(f"   Body: {error_body}")
        print(f"❌ Erro HTTP ao criar collector-config: {e.code} - {error_body}")
        raise
    except urllib.error.URLError as e:
        print(f"❌ Erro de conexão ao criar collector-config: {e.reason}")
        raise

    try:
        response_json = json.loads(body) if body else {}
    except json.JSONDecodeError:
        print(f"❌ Resposta inválida ao criar collector-config: {body}")
        raise

    collector_config_id = response_json.get("id")
    if collector_config_id is None:
        print(f"❌ A resposta não contém $.id para collector-config: {response_json}")
        raise ValueError("ID do collector-config não encontrado na resposta")

    return collector_config_id


def carregar_config_ids(caminho_config):
    """Carrega IDs de métricas do arquivo de configuração."""
    if not caminho_config.exists():
        return {
            "metrics": {},
            "microservices": {},
            "collectors": {},
            "collectorConfigs": {},
        }

    try:
        with caminho_config.open("r", encoding="utf-8") as f:
            dados = json.load(f)
            return normalizar_config_ids(dados)
    except (json.JSONDecodeError, OSError):
        print(f"⚠️ Não foi possível ler {caminho_config.name}. Um novo arquivo será gerado.")
        return {
            "metrics": {},
            "microservices": {},
            "collectors": {},
            "collectorConfigs": {},
        }


def normalizar_config_ids(dados):
    """Normaliza config para o formato com seções, mantendo compatibilidade com formato antigo."""
    estrutura_base = {
        "metrics": {},
        "microservices": {},
        "collectors": {},
        "collectorConfigs": {},
    }

    if not isinstance(dados, dict):
        return estrutura_base

    for secao in estrutura_base:
        valor_secao = dados.get(secao)
        if isinstance(valor_secao, dict):
            estrutura_base[secao].update(valor_secao)

    for chave, valor in dados.items():
        if chave in estrutura_base:
            continue
        secao = CHAVE_PARA_SECAO.get(chave)
        if secao:
            estrutura_base[secao][chave] = valor

    return estrutura_base


def obter_config_id(config, chave):
    """Obtém ID por chave no novo formato e com fallback para estruturas antigas."""
    secao = CHAVE_PARA_SECAO.get(chave)
    if secao and isinstance(config.get(secao), dict):
        valor = config[secao].get(chave)
        if valor:
            return valor

    for secao_nome in ["metrics", "microservices", "collectors", "collectorConfigs"]:
        secao_dict = config.get(secao_nome)
        if isinstance(secao_dict, dict) and chave in secao_dict:
            return secao_dict[chave]

    return config.get(chave)


def definir_config_id(config, chave, valor):
    """Define ID em sua seção apropriada no novo formato."""
    secao = CHAVE_PARA_SECAO.get(chave)
    if secao is None:
        config[chave] = valor
        return
    if secao not in config or not isinstance(config.get(secao), dict):
        config[secao] = {}
    config[secao][chave] = valor


def salvar_config_ids(caminho_config, dados):
    """Salva IDs de métricas no arquivo de configuração."""
    dados_normalizados = normalizar_config_ids(dados)
    with caminho_config.open("w", encoding="utf-8") as f:
        json.dump(dados_normalizados, f, ensure_ascii=False, indent=2)


ARQUIVO_CONFIG_METRICAS = Path(__file__).resolve().with_name("metrics_config.json")

# Entrada do usuário
entrada_usuario = input("📁 Digite o caminho raiz onde as pastas serão criadas (ou atualizadas): ")
pasta_raiz = Path(entrada_usuario).expanduser().resolve()
pasta_raiz.mkdir(parents=True, exist_ok=True)
print(f"✅ Diretório base: {pasta_raiz}\n" + "="*40)

pastas_dos_projetos = []

# ==========================================
# ETAPA 1: Criar categorias, Clonar ou Atualizar
# ==========================================
print("🔄 ETAPA 1: Estruturando pastas, clonando e atualizando repositórios...")

try:
    for categoria, urls in REPOSITORIOS.items():
        print(f"\n📂 Processando categoria: [{categoria}]")
        caminho_categoria = pasta_raiz / categoria
        caminho_categoria.mkdir(parents=True, exist_ok=True)
        
        for repo_url in urls:
            dir_name = repo_url.rstrip('/').split('/')[-1].replace('.git', '')
            caminho_projeto = caminho_categoria / dir_name
            
            print(f"  📦 Projeto: {dir_name}")
            
            if not caminho_projeto.exists():
                # Nova clonagem
                run_command(["git", "clone", repo_url, str(caminho_projeto)])
            else:
                # Atualização (Pasta já existe)
                print(f"    🔄 Pasta já existe. Atualizando com 'git pull'...")
                run_command(["git", "pull"], cwd=caminho_projeto)
            
            pastas_dos_projetos.append(caminho_projeto)

except subprocess.CalledProcessError:
    print("\n🚨 ERRO: Falha durante o download ou atualização do Git.")
    print("🛑 Script interrompido. Verifique os erros acima (ex: conflitos no git pull ou falta de permissão).")
    sys.exit(1)

print("\n" + "="*40)

# ==========================================
# ETAPA 2: Subir os contêineres com Rollback em caso de erro
# ==========================================
print("🔄 ETAPA 2: Subindo os contêineres...")
projetos_iniciados = []

try:
    for caminho_projeto in pastas_dos_projetos:
        print(f"\n🐳 Subindo: {caminho_projeto.parent.name} / {caminho_projeto.name}")

        if args.limpar_banco_dados:
            print("🧹 Flag --limpar-banco-dados ativa: removendo volumes para iniciar com banco limpo...")
            # Usa check=False porque alguns projetos podem não estar rodando ainda.
            subprocess.run(
                ["docker", "compose", "down", "-v"],
                cwd=caminho_projeto,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )

        run_command(["docker", "compose", "up", "--build", "-d"], cwd=caminho_projeto)
        
        # Adiciona à lista de projetos que subiram com sucesso (ou que tentaram subir)
        projetos_iniciados.append(caminho_projeto)

except subprocess.CalledProcessError:
    print("\n" + "!"*40)
    print("🚨 ERRO GRAVE: Falha ao tentar subir os contêineres!")
    print("🛑 Acionando protocolo de segurança: Parando os contêineres iniciados para evitar estado inconsistente...")
    
    # Se o projeto atual falhou, garantimos que ele está na lista para ser derrubado também
    if caminho_projeto not in projetos_iniciados:
        projetos_iniciados.append(caminho_projeto)
    
    # Faz o loop reverso (do último pro primeiro) derrubando tudo
    for p in reversed(projetos_iniciados):
        print(f"  🔻 Derrubando contêineres de: {p.name}...")
        # Aqui não usamos o run_command pois não queremos que o script pare se o 'down' der erro
        subprocess.run(["docker", "compose", "down"], cwd=p, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    print("!"*40)
    print("❌ Script finalizado com falhas. O ambiente foi limpo.")
    sys.exit(1)

print("\n" + "="*40)
print("🎉 Sucesso Absoluto! Toda a estrutura foi validada, atualizada e os contêineres estão rodando perfeitamente.")

if args.limpar_banco_dados:
    print("🧹 Limpando IDs salvos em configuração para evitar reuso após limpeza do banco...")
    salvar_config_ids(ARQUIVO_CONFIG_METRICAS, normalizar_config_ids({}))
    print(f"💾 Arquivo de configuração reiniciado: {ARQUIVO_CONFIG_METRICAS}")

# ==========================================
# ETAPA 3: Criar métricas base no MetricHub
# ==========================================
print("\n🔄 ETAPA 3: Criando métricas base...")

payload_number_of_endpoints = {
    "name": "Number of endpoints",
    "description": "Number of endpoints in a service that implements a Rest API",
    "type": "absolute",
}

payload_database_connections = {
    "name": "Number of Database Connections",
    "description": "Number of database connections made by a microservice",
    "type": "absolute",
}

try:
    config_metricas = carregar_config_ids(ARQUIVO_CONFIG_METRICAS)
    houve_alteracao_config = False

    if args.forcar_recriacao_ids:
        print("🔁 Modo forçado ativado: recriando IDs das métricas...")
        idNumberofEndpointsMetric = criar_metrica(payload_number_of_endpoints)
        idDatabaseConnectionsMetric = criar_metrica(payload_database_connections)
        definir_config_id(config_metricas, "idNumberofEndpointsMetric", idNumberofEndpointsMetric)
        definir_config_id(config_metricas, "idDatabaseConnectionsMetric", idDatabaseConnectionsMetric)
        houve_alteracao_config = True
    else:
        idNumberofEndpointsMetric = obter_config_id(config_metricas, "idNumberofEndpointsMetric")
        if idNumberofEndpointsMetric:
            print("♻️ Reutilizando idNumberofEndpointsMetric salvo em configuração.")
        else:
            idNumberofEndpointsMetric = criar_metrica(payload_number_of_endpoints)
            definir_config_id(config_metricas, "idNumberofEndpointsMetric", idNumberofEndpointsMetric)
            houve_alteracao_config = True

        idDatabaseConnectionsMetric = obter_config_id(config_metricas, "idDatabaseConnectionsMetric")
        if idDatabaseConnectionsMetric:
            print("♻️ Reutilizando idDatabaseConnectionsMetric salvo em configuração.")
        else:
            idDatabaseConnectionsMetric = criar_metrica(payload_database_connections)
            definir_config_id(config_metricas, "idDatabaseConnectionsMetric", idDatabaseConnectionsMetric)
            houve_alteracao_config = True

    if houve_alteracao_config:
        salvar_config_ids(ARQUIVO_CONFIG_METRICAS, config_metricas)
        print(f"💾 IDs salvos em: {ARQUIVO_CONFIG_METRICAS}")
except Exception as e:
    print(f"❌ Não foi possível criar todas as métricas base: {e}")
    sys.exit(1)

print(f"✅ idNumberofEndpointsMetric: {idNumberofEndpointsMetric}")
print(f"✅ idDatabaseConnectionsMetric: {idDatabaseConnectionsMetric}")

# ==========================================
# ETAPA 4: Criar microserviços base
# ==========================================
print("\n🔄 ETAPA 4: Criando microserviços base...")

payload_amaris_contabil = {
    "name": "Amaris Contabil",
    "metadatas": [
        {
            "varName": "urlOpenApiFile",
            "varValue": "http://host.docker.internal:8091/swagger/v1/swagger.json",
        },
        {
            "varName": "urlControllers",
            "varValue": "https://github.com/brunopromano/painel-contabil/tree/main/PainelContabil.API/Controllers",
        },
        {
            "varName": "urlLog",
            "varValue": "http://host.docker.internal:8091/api/v1/logs",
        },
    ],
}

payload_finance_users = {
    "name": "Finance Users",
    "metadatas": [
        {
            "varName": "urlOpenApiFile",
            "varValue": "http://host.docker.internal:8093/v3/api-docs",
        },
        {
            "varName": "urlControllers",
            "varValue": "https://github.com/brunopromano/finance-users-api/tree/main/src/main/java/com/finance/users/presentation/controller",
        },
        {
            "varName": "urlLog",
            "varValue": "http://host.docker.internal:8093/api/v1/logs",
        },
    ],
}

payload_painel_contabil = {
    "name": "Painel Contábil",
    "metadatas": [
        {
            "varName": "urlOpenApiFile",
            "varValue": "http://host.docker.internal:5001/swagger/v1/swagger.json",
        },
        {
            "varName": "urlControllers",
            "varValue": "https://github.com/brunopromano/painel-contabil/tree/main/PainelContabil.API/Controllers",
        },
        {
            "varName": "urlLog",
            "varValue": "http://host.docker.internal:5001/api/v1/logs?tail=100",
        },
    ],
}

try:
    config_metricas = carregar_config_ids(ARQUIVO_CONFIG_METRICAS)
    houve_alteracao_config = False

    if args.forcar_recriacao_ids:
        print("🔁 Modo forçado ativado: recriando IDs dos microserviços...")
        idAmarisContabilMicroservice = criar_microservico(payload_amaris_contabil)
        idFinanceUsersMicroservice = criar_microservico(payload_finance_users)
        idPainelContabilMicroservice = criar_microservico(payload_painel_contabil)
        definir_config_id(config_metricas, "idAmarisContabilMicroservice", idAmarisContabilMicroservice)
        definir_config_id(config_metricas, "idFinanceUsersMicroservice", idFinanceUsersMicroservice)
        definir_config_id(config_metricas, "idPainelContabilMicroservice", idPainelContabilMicroservice)
        houve_alteracao_config = True
    else:
        idAmarisContabilMicroservice = obter_config_id(config_metricas, "idAmarisContabilMicroservice")
        if idAmarisContabilMicroservice:
            print("♻️ Reutilizando idAmarisContabilMicroservice salvo em configuração.")
        else:
            idAmarisContabilMicroservice = criar_microservico(payload_amaris_contabil)
            definir_config_id(config_metricas, "idAmarisContabilMicroservice", idAmarisContabilMicroservice)
            houve_alteracao_config = True

        idFinanceUsersMicroservice = obter_config_id(config_metricas, "idFinanceUsersMicroservice")
        if idFinanceUsersMicroservice:
            print("♻️ Reutilizando idFinanceUsersMicroservice salvo em configuração.")
        else:
            idFinanceUsersMicroservice = criar_microservico(payload_finance_users)
            definir_config_id(config_metricas, "idFinanceUsersMicroservice", idFinanceUsersMicroservice)
            houve_alteracao_config = True

        idPainelContabilMicroservice = obter_config_id(config_metricas, "idPainelContabilMicroservice")
        if idPainelContabilMicroservice:
            print("♻️ Reutilizando idPainelContabilMicroservice salvo em configuração.")
        else:
            idPainelContabilMicroservice = criar_microservico(payload_painel_contabil)
            definir_config_id(config_metricas, "idPainelContabilMicroservice", idPainelContabilMicroservice)
            houve_alteracao_config = True

    if houve_alteracao_config:
        salvar_config_ids(ARQUIVO_CONFIG_METRICAS, config_metricas)
        print(f"💾 IDs salvos em: {ARQUIVO_CONFIG_METRICAS}")
except Exception as e:
    print(f"❌ Não foi possível criar todos os microserviços base: {e}")
    sys.exit(1)

print(f"✅ idAmarisContabilMicroservice: {idAmarisContabilMicroservice}")
print(f"✅ idFinanceUsersMicroservice: {idFinanceUsersMicroservice}")
print(f"✅ idPainelContabilMicroservice: {idPainelContabilMicroservice}")

# ==========================================
# ETAPA 5: Criar collectors base
# ==========================================
print("\n🔄 ETAPA 5: Criando collectors base...")

payload_openapi_endpoints_collector = {
    "name": "OpenAPI Endpoints Collector",
    "description": "Collector to count operations from OpenAPI specification",
    "collectionMethod": "openapi",
    "metricId": idNumberofEndpointsMetric,
    "metadata": [
        {
            "keyName": "url",
            "keyValue": "http://host.docker.internal:8081/collector",
        },
        {
            "keyName": "requestSchema",
            "keyValue": "{\"type\":\"object\",\"properties\":{\"urlOpenApiFile\":{\"type\":\"string\",\"format\":\"uri\"}},\"required\":[\"urlOpenApiFile\"]}",
        },
        {
            "keyName": "httpMethod",
            "keyValue": "POST",
        },
        {
            "keyName": "pathToMetric",
            "keyValue": "$.measurement.value",
        },
    ],
    "responseSchemas": [
        {
            "schema": "{\"type\":\"object\",\"properties\":{\"metric\":{\"type\":\"object\",\"properties\":{\"name\":{\"type\":\"string\"},\"collectorStrategy\":{\"type\":\"string\"}}},\"measurement\":{\"type\":\"object\",\"properties\":{\"apiIdentifier\":{\"type\":\"string\"},\"value\":{\"type\":\"number\"},\"unit\":{\"type\":\"string\"},\"timestamp\":{\"type\":\"string\"}}}}}",
            "statusType": 200,
            "description": "Successful response with metric and measurement data",
        }
    ],
}

payload_source_code_collector = {
    "name": "Source Code Collector",
    "description": "Collector to count operations from a repo in Github",
    "collectionMethod": "source code",
    "metricId": idNumberofEndpointsMetric,
    "metadata": [
        {
            "keyName": "url",
            "keyValue": "http://host.docker.internal:8082/collect",
        },
        {
            "keyName": "requestSchema",
            "keyValue": "{\"type\":\"object\",\"properties\":{\"urlControllers\":{\"type\":\"string\",\"format\":\"uri\"}},\"required\":[\"urlControllers\"]}",
        },
        {
            "keyName": "httpMethod",
            "keyValue": "POST",
        },
        {
            "keyName": "pathToMetric",
            "keyValue": "$.measurement.value",
        },
    ],
    "responseSchemas": [
        {
            "schema": "{\"type\":\"object\",\"properties\":{\"metric\":{\"type\":\"object\",\"properties\":{\"name\":{\"type\":\"string\"},\"collectorStrategy\":{\"type\":\"string\"}}},\"measurement\":{\"type\":\"object\",\"properties\":{\"apiIdentifier\":{\"type\":\"string\"},\"value\":{\"type\":\"number\"},\"unit\":{\"type\":\"string\"},\"timestamp\":{\"type\":\"string\"}}}}}",
            "statusType": 200,
            "description": "Successful response with metric and measurement data",
        }
    ],
}

payload_log_metric_operations_collector = {
    "name": "Log Metric Operations Collector",
    "description": "Collector to count operations from logs of an application",
    "collectionMethod": "logs",
    "metricId": idDatabaseConnectionsMetric,
    "metadata": [
        {
            "keyName": "url",
            "keyValue": "http://host.docker.internal:8083/api/collect?start={startDateTime}&end={endDateTime}",
        },
        {
            "keyName": "requestSchema",
            "keyValue": "{\"type\":\"object\",\"properties\":{\"urlLog\":{\"type\":\"string\",\"format\":\"uri\"}},\"required\":[\"urlLog\"]}",
        },
        {
            "keyName": "httpMethod",
            "keyValue": "POST",
        },
        {
            "keyName": "pathToMetric",
            "keyValue": "$.measurement.value",
        },
    ],
    "responseSchemas": [
        {
            "schema": "{\"type\":\"object\",\"properties\":{\"metric\":{\"type\":\"object\",\"properties\":{\"name\":{\"type\":\"string\"},\"collectorStrategy\":{\"type\":\"string\"}}},\"measurement\":{\"type\":\"object\",\"properties\":{\"apiIdentifier\":{\"type\":\"string\"},\"value\":{\"type\":\"number\"},\"unit\":{\"type\":\"string\"},\"timestamp\":{\"type\":\"string\"}}}}}",
            "statusType": 200,
            "description": "Successful response with metric and measurement data",
        }
    ],
}

payload_code_db_connections_collector = {
    "name": "Code DB Connections",
    "description": "Collector to count database connections from a repository in Github",
    "collectionMethod": "code",
    "metricId": idDatabaseConnectionsMetric,
    "metadata": [
        {
            "keyName": "url",
            "keyValue": "http://host.docker.internal:8084/collect",
        },
        {
            "keyName": "requestSchema",
            "keyValue": "{\"type\":\"object\",\"properties\":{\"repositoryUrl\":{\"type\":\"string\"}},\"required\":[\"repositoryUrl\"]}",
        },
        {
            "keyName": "httpMethod",
            "keyValue": "POST",
        },
        {
            "keyName": "pathToMetric",
            "keyValue": "$.measurement.value",
        },
    ],
    "responseSchemas": [
        {
            "schema": "{\"type\":\"object\",\"properties\":{\"metric\":{\"type\":\"object\",\"properties\":{\"name\":{\"type\":\"string\"},\"collectorStrategy\":{\"type\":\"string\"}}},\"measurement\":{\"type\":\"object\",\"properties\":{\"apiIdentifier\":{\"type\":\"string\"},\"value\":{\"type\":\"number\"},\"unit\":{\"type\":\"string\"},\"timestamp\":{\"type\":\"string\"}}}}}",
            "statusType": 200,
            "description": "Successful response with metric and measurement data",
        }
    ],
}

payload_docker_compose_db_conns_collector = {
    "name": "Docker compose DB Conns",
    "description": "Collector to count database connections from a repository with docker compose",
    "collectionMethod": "docker compose",
    "metricId": idDatabaseConnectionsMetric,
    "metadata": [
        {
            "keyName": "url",
            "keyValue": "http://host.docker.internal:8084/collect",
        },
        {
            "keyName": "requestSchema",
            "keyValue": "{\"type\":\"object\",\"properties\":{\"repositoryUrl\":{\"type\":\"string\"},\"dockerComposeAnalysis\":{\"type\":\"boolean\"}},\"required\":[\"repositoryUrl\",\"dockerComposeAnalysis\"]}",
        },
        {
            "keyName": "httpMethod",
            "keyValue": "POST",
        },
        {
            "keyName": "pathToMetric",
            "keyValue": "$.measurement.value",
        },
    ],
    "responseSchemas": [
        {
            "schema": "{\"type\":\"object\",\"properties\":{\"metric\":{\"type\":\"object\",\"properties\":{\"name\":{\"type\":\"string\"},\"collectorStrategy\":{\"type\":\"string\"}}},\"measurement\":{\"type\":\"object\",\"properties\":{\"apiIdentifier\":{\"type\":\"string\"},\"value\":{\"type\":\"number\"},\"unit\":{\"type\":\"string\"},\"timestamp\":{\"type\":\"string\"}}}}}",
            "statusType": 200,
            "description": "Successful response with metric and measurement data",
        }
    ],
}

payload_log_metric_operations_collector_8084 = {
    "name": "Log Metric Operations Collector",
    "description": "Collector to count operations from logs of an application",
    "collectionMethod": "logs",
    "metricId": idDatabaseConnectionsMetric,
    "metadata": [
        {
            "keyName": "url",
            "keyValue": "http://host.docker.internal:8084/api/collect",
        },
        {
            "keyName": "requestSchema",
            "keyValue": "{\"type\":\"object\",\"properties\":{\"urlLog\":{\"type\":\"string\",\"format\":\"uri\"}},\"required\":[\"urlLog\"]}",
        },
        {
            "keyName": "httpMethod",
            "keyValue": "POST",
        },
        {
            "keyName": "pathToMetric",
            "keyValue": "$.measurement.value",
        },
    ],
    "responseSchemas": [
        {
            "schema": "{\"type\":\"object\",\"properties\":{\"metric\":{\"type\":\"object\",\"properties\":{\"name\":{\"type\":\"string\"},\"collectorStrategy\":{\"type\":\"string\"}}},\"measurement\":{\"type\":\"object\",\"properties\":{\"apiIdentifier\":{\"type\":\"string\"},\"value\":{\"type\":\"number\"},\"unit\":{\"type\":\"string\"},\"timestamp\":{\"type\":\"string\"}}}}}",
            "statusType": 200,
            "description": "Successful response with metric and measurement data",
        }
    ],
}

try:
    config_metricas = carregar_config_ids(ARQUIVO_CONFIG_METRICAS)
    houve_alteracao_config = False

    if args.forcar_recriacao_ids:
        print("🔁 Modo forçado ativado: recriando IDs dos collectors...")
        idOpenApiEndpointsCollector = criar_collector(payload_openapi_endpoints_collector)
        idSourceCodeCollector = criar_collector(payload_source_code_collector)
        idLogMetricOperationsCollector = criar_collector(payload_log_metric_operations_collector)
        idCodeDbConnectionsCollector = criar_collector(payload_code_db_connections_collector)
        idDockerComposeDbConnsCollector = criar_collector(payload_docker_compose_db_conns_collector)
        idLogDBMetricOperationsCollector = criar_collector(payload_log_metric_operations_collector_8084)
        definir_config_id(config_metricas, "idOpenApiEndpointsCollector", idOpenApiEndpointsCollector)
        definir_config_id(config_metricas, "idSourceCodeCollector", idSourceCodeCollector)
        definir_config_id(config_metricas, "idLogMetricOperationsCollector", idLogMetricOperationsCollector)
        definir_config_id(config_metricas, "idCodeDbConnectionsCollector", idCodeDbConnectionsCollector)
        definir_config_id(config_metricas, "idDockerComposeDbConnsCollector", idDockerComposeDbConnsCollector)
        definir_config_id(config_metricas, "idLogDBMetricOperationsCollector", idLogDBMetricOperationsCollector)
        houve_alteracao_config = True
    else:
        idOpenApiEndpointsCollector = obter_config_id(config_metricas, "idOpenApiEndpointsCollector")
        if idOpenApiEndpointsCollector:
            print("♻️ Reutilizando idOpenApiEndpointsCollector salvo em configuração.")
        else:
            idOpenApiEndpointsCollector = criar_collector(payload_openapi_endpoints_collector)
            definir_config_id(config_metricas, "idOpenApiEndpointsCollector", idOpenApiEndpointsCollector)
            houve_alteracao_config = True

        idSourceCodeCollector = obter_config_id(config_metricas, "idSourceCodeCollector")
        if idSourceCodeCollector:
            print("♻️ Reutilizando idSourceCodeCollector salvo em configuração.")
        else:
            idSourceCodeCollector = criar_collector(payload_source_code_collector)
            definir_config_id(config_metricas, "idSourceCodeCollector", idSourceCodeCollector)
            houve_alteracao_config = True

        idLogMetricOperationsCollector = obter_config_id(config_metricas, "idLogMetricOperationsCollector")
        if idLogMetricOperationsCollector:
            print("♻️ Reutilizando idLogMetricOperationsCollector salvo em configuração.")
        else:
            idLogMetricOperationsCollector = criar_collector(payload_log_metric_operations_collector)
            definir_config_id(config_metricas, "idLogMetricOperationsCollector", idLogMetricOperationsCollector)
            houve_alteracao_config = True

        idCodeDbConnectionsCollector = obter_config_id(config_metricas, "idCodeDbConnectionsCollector")
        if idCodeDbConnectionsCollector:
            print("♻️ Reutilizando idCodeDbConnectionsCollector salvo em configuração.")
        else:
            idCodeDbConnectionsCollector = criar_collector(payload_code_db_connections_collector)
            definir_config_id(config_metricas, "idCodeDbConnectionsCollector", idCodeDbConnectionsCollector)
            houve_alteracao_config = True

        idDockerComposeDbConnsCollector = obter_config_id(config_metricas, "idDockerComposeDbConnsCollector")
        if idDockerComposeDbConnsCollector:
            print("♻️ Reutilizando idDockerComposeDbConnsCollector salvo em configuração.")
        else:
            idDockerComposeDbConnsCollector = criar_collector(payload_docker_compose_db_conns_collector)
            definir_config_id(config_metricas, "idDockerComposeDbConnsCollector", idDockerComposeDbConnsCollector)
            houve_alteracao_config = True

        idLogDBMetricOperationsCollector = obter_config_id(config_metricas, "idLogDBMetricOperationsCollector")
        if idLogDBMetricOperationsCollector:
            print("♻️ Reutilizando idLogDBMetricOperationsCollector salvo em configuração.")
        else:
            idLogDBMetricOperationsCollector = criar_collector(payload_log_metric_operations_collector_8084)
            definir_config_id(config_metricas, "idLogDBMetricOperationsCollector", idLogDBMetricOperationsCollector)
            houve_alteracao_config = True

    if houve_alteracao_config:
        salvar_config_ids(ARQUIVO_CONFIG_METRICAS, config_metricas)
        print(f"💾 IDs salvos em: {ARQUIVO_CONFIG_METRICAS}")
except Exception as e:
    print(f"❌ Não foi possível criar os collectors base: {e}")
    sys.exit(1)

print(f"✅ idOpenApiEndpointsCollector: {idOpenApiEndpointsCollector}")
print(f"✅ idSourceCodeCollector: {idSourceCodeCollector}")
print(f"✅ idLogMetricOperationsCollector: {idLogMetricOperationsCollector}")
print(f"✅ idCodeDbConnectionsCollector: {idCodeDbConnectionsCollector}")
print(f"✅ idDockerComposeDbConnsCollector: {idDockerComposeDbConnsCollector}")
print(f"✅ idLogDBMetricOperationsCollector: {idLogDBMetricOperationsCollector}")

# ==========================================
# ETAPA 6: Criar configurações de coleta
# ==========================================
print("\n🔄 ETAPA 6: Criando configurações de coleta...")

COLLECTOR_CONFIGS_SPEC = [
    ("idOpenApiAmarisCollectorConfig",              idOpenApiEndpointsCollector,      idAmarisContabilMicroservice,  "0 */5 * * * *"),
    ("idOpenApiFinanceUsersCollectorConfig",         idOpenApiEndpointsCollector,      idFinanceUsersMicroservice,    "0 */5 * * * *"),
    ("idOpenApiPainelContabilCollectorConfig",       idOpenApiEndpointsCollector,      idPainelContabilMicroservice,  "0 */5 * * * *"),
    ("idSourceCodeAmarisCollectorConfig",            idSourceCodeCollector,            idAmarisContabilMicroservice,  "0 */10 * * * *"),
    ("idSourceCodeFinanceUsersCollectorConfig",      idSourceCodeCollector,            idFinanceUsersMicroservice,    "0 */10 * * * *"),
    ("idSourceCodePainelContabilCollectorConfig",    idSourceCodeCollector,            idPainelContabilMicroservice,  "0 */10 * * * *"),
    ("idLogMetricAmarisCollectorConfig",             idLogMetricOperationsCollector,   idAmarisContabilMicroservice,  "0 */15 * * * *"),
    ("idLogMetricFinanceUsersCollectorConfig",       idLogMetricOperationsCollector,   idFinanceUsersMicroservice,    "0 */15 * * * *"),
    ("idLogMetricPainelContabilCollectorConfig",     idLogMetricOperationsCollector,   idPainelContabilMicroservice,  "0 */15 * * * *"),
    ("idCodeDbAmarisCollectorConfig",                idCodeDbConnectionsCollector,     idAmarisContabilMicroservice,  "0 */10 * * * *"),
    ("idCodeDbFinanceUsersCollectorConfig",          idCodeDbConnectionsCollector,     idFinanceUsersMicroservice,    "0 */10 * * * *"),
    ("idCodeDbPainelContabilCollectorConfig",        idCodeDbConnectionsCollector,     idPainelContabilMicroservice,  "0 */10 * * * *"),
    ("idDockerComposeAmarisCollectorConfig",         idDockerComposeDbConnsCollector,  idAmarisContabilMicroservice,  "0 */10 * * * *"),
    ("idDockerComposeFinanceUsersCollectorConfig",   idDockerComposeDbConnsCollector,  idFinanceUsersMicroservice,    "0 */10 * * * *"),
    ("idDockerComposePainelContabilCollectorConfig", idDockerComposeDbConnsCollector,  idPainelContabilMicroservice,  "0 */10 * * * *"),
    ("idLogDBMetricAmarisCollectorConfig",           idLogDBMetricOperationsCollector, idAmarisContabilMicroservice,  "0 */15 * * * *"),
    ("idLogDBMetricFinanceUsersCollectorConfig",     idLogDBMetricOperationsCollector, idFinanceUsersMicroservice,    "0 */15 * * * *"),
    ("idLogDBMetricPainelContabilCollectorConfig",   idLogDBMetricOperationsCollector, idPainelContabilMicroservice,  "0 */15 * * * *"),
]

try:
    config_metricas = carregar_config_ids(ARQUIVO_CONFIG_METRICAS)
    houve_alteracao_config = False
    collector_config_ids = {}

    for chave, collector_id, microservice_id, cron in COLLECTOR_CONFIGS_SPEC:
        id_existente = obter_config_id(config_metricas, chave)
        if id_existente and not args.forcar_recriacao_ids:
            print(f"♻️ Reutilizando {chave} salvo em configuração.")
            collector_config_ids[chave] = id_existente
        else:
            if args.forcar_recriacao_ids:
                print(f"🔁 Modo forçado ativado: recriando {chave}...")
            now = datetime.now(timezone.utc)
            payload = {
                "collectorId": collector_id,
                "microserviceId": microservice_id,
                "cronExpression": cron,
                "startDateTime": now.replace(microsecond=0).isoformat(),
                "endDateTime": (now + timedelta(minutes=30)).replace(microsecond=0).isoformat(),
            }
            novo_id = criar_collector_config(payload)
            collector_config_ids[chave] = novo_id
            definir_config_id(config_metricas, chave, novo_id)
            salvar_config_ids(ARQUIVO_CONFIG_METRICAS, config_metricas)
            houve_alteracao_config = True

    if houve_alteracao_config:
        print(f"💾 IDs salvos em: {ARQUIVO_CONFIG_METRICAS}")
except Exception as e:
    print(f"❌ Não foi possível criar a configuração de coleta: {e}")
    sys.exit(1)

for chave, *_ in COLLECTOR_CONFIGS_SPEC:
    print(f"✅ {chave}: {collector_config_ids[chave]}")