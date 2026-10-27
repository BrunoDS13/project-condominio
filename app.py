import os
import secrets
import sqlite3
from datetime import datetime, timedelta

from flask import Flask, abort, flash, redirect, render_template, request, url_for

from condominio import db, regras, seed, servicos

DIAS_DA_SEMANA = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"]
MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
DIAS_NO_SELETOR = 14


def formatar_data(iso):
    """'2026-11-10' -> 'ter, 10 nov'"""
    dia = datetime.strptime(iso, "%Y-%m-%d")
    return f"{DIAS_DA_SEMANA[dia.weekday()]}, {dia.day} {MESES[dia.month - 1]}"


def criar_app(caminho_banco=db.CAMINHO_PADRAO, agora=datetime.now):
    """`agora` devolve o momento atual; os testes passam um horário fixo no lugar."""
    app = Flask(__name__)
    # Em produção defina SECRET_KEY. Sem ela, usa-se uma chave aleatória (os avisos pendentes se perdem ao reiniciar).
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
    app.config["CAMINHO_BANCO"] = caminho_banco
    app.jinja_env.filters["data_curta"] = formatar_data

    def conexao():
        return db.conectar(app.config["CAMINHO_BANCO"])

    def hoje_iso():
        return agora().strftime("%Y-%m-%d")

    @app.route("/")
    def index():
        con = conexao()
        areas = db.listar_areas(con)
        reservas_de_hoje = db.listar_reservas(con, status=db.STATUS_CONFIRMADA, data=hoje_iso())
        futuras = db.listar_reservas(con, status=db.STATUS_CONFIRMADA, a_partir_de=hoje_iso())
        con.close()

        agora_texto = agora().strftime("%Y-%m-%d %H:%M")
        cartoes = []
        for area in areas:
            do_dia = [r for r in reservas_de_hoje if r["area_id"] == area["id"]]
            proxima = next(
                (r for r in futuras if r["area_id"] == area["id"] and f"{r['data']} {r['fim']}" > agora_texto), None
            )
            cartoes.append(
                {"area": area, "segmentos": regras.segmentos_do_dia(area, do_dia), "proxima": proxima}
            )
        return render_template("index.html", cartoes=cartoes, proximas=futuras[:6], hoje=hoje_iso())

    return app


app = criar_app()

if __name__ == "__main__":
    _con = db.conectar()
    seed.carregar_dados_ficticios(_con)  # só age se o banco estiver vazio
    _con.close()
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")
