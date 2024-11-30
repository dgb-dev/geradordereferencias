from flask import Flask, request, render_template_string, redirect, url_for, session
from googlesearch import search
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import random
import re
from functools import lru_cache

app = Flask(__name__)
app.secret_key = "sua_chave_secreta_aqui"  # Alterar para algo seguro em produção

# Lista de User-Agents para evitar bloqueios
user_agents = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
]

# Lista de sites problemáticos a serem ignorados
ignorar_sites = ["sigmaaldrich.com"]

# Cache para evitar requisições duplicadas
@lru_cache(maxsize=100)
def buscar_na_web(tema, num_links=10):
    links = []
    try:
        for link in search(tema, num_results=num_links):
            if any(site in link for site in ignorar_sites):
                continue
            links.append(link)
    except Exception as e:
        print(f"Erro ao buscar na web: {e}")
    return links

def processar_link(link):
    try:
        headers = {"User-Agent": random.choice(user_agents)}
        response = requests.get(link, headers=headers, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            title = soup.title.string.strip() if soup.title else "Título não disponível"
            return f"{title}. Disponível em: <{link}>. Acesso em: {data_atual()}."
    except Exception as e:
        print(f"Erro ao processar {link}: {e}")
    return None

def data_atual():
    return datetime.now().strftime("%d de %B de %Y")

def gerar_referencias(links):
    referencias = []
    with ThreadPoolExecutor() as executor:
        futures = [executor.submit(processar_link, link) for link in links]
        for future in futures:
            resultado = future.result()
            if resultado:
                referencias.append(resultado)
    return referencias

def filtrar_links(links, filtro):
    if filtro == "PDFs":
        return [link for link in links if re.search(r"\.pdf$", link, re.IGNORECASE)]
    elif filtro == "Sites":
        return [link for link in links if not re.search(r"\.pdf$", link, re.IGNORECASE)]
    return links

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="pt-br">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Referências sobre {{ tema }}</title>
    <link rel="stylesheet" href="/static/style.css">
</head>
<body>
    <div class="container">
        <h1>Referências sobre: {{ tema }}</h1>
        <form action="/" method="post">
            <input type="text" name="tema" placeholder="Digite o tema" required>
            <div>
                <label><input type="radio" name="filtro" value="Todos" checked> Todos</label>
                <label><input type="radio" name="filtro" value="PDFs"> PDFs</label>
                <label><input type="radio" name="filtro" value="Sites"> Sites</label>
            </div>
            <button type="submit">Pesquisar</button>
        </form>
        {% if links %}
        <h2>Resultados Encontrados:</h2>
        <ul>
            {% for link in links %}
            <li>
                <a href="{{ link }}" target="_blank">{{ link }}</a>
            </li>
            {% endfor %}
        </ul>
        {% endif %}
        {% if referencias %}
        <h2>Referências Formatadas:</h2>
        <ul>
            {% for ref in referencias %}
            <li>{{ ref }}</li>
            {% endfor %}
        </ul>
        {% endif %}
        <hr>
        <h2>Histórico de Pesquisas</h2>
        {% if historico %}
            {% for item in historico %}
            <details>
                <summary>{{ item.data }} - Tema: {{ item.tema }}</summary>
                <ul>
                    {% for ref in item.referencias %}
                    <li>{{ ref }}</li>
                    {% endfor %}
                </ul>
                <form action="/remover_historico" method="post" style="display:inline;">
                    <input type="hidden" name="indice" value="{{ loop.index0 }}">
                    <button type="submit">Remover</button>
                </form>
            </details>
            {% endfor %}
        {% else %}
            <p>Nenhum histórico disponível.</p>
        {% endif %}
    </div>
</body>
</html>
"""

@app.route("/", methods=["GET", "POST"])
def home():
    if "historico" not in session:
        session["historico"] = []

    if request.method == "POST":
        tema = request.form["tema"]
        filtro = request.form.get("filtro")

        links = buscar_na_web(tema, num_links=15)
        links = filtrar_links(links, filtro)
        referencias = gerar_referencias(links)

        session["historico"].append({
            "tema": tema,
            "referencias": referencias,
            "data": data_atual()
        })
        session.modified = True

        return render_template_string(HTML_TEMPLATE, tema=tema, links=links, referencias=referencias, historico=session["historico"])

    return render_template_string(HTML_TEMPLATE, tema="Nenhum", links=None, referencias=None, historico=session["historico"])

@app.route("/remover_historico", methods=["POST"])
def remover_historico():
    indice = int(request.form["indice"])
    if "historico" in session and 0 <= indice < len(session["historico"]):
        session["historico"].pop(indice)
        session.modified = True
    return redirect(url_for("home"))

if __name__ == "__main__":
    from waitress import serve
    serve(app, host="0.0.0.0", port=8080)
