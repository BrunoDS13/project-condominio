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

    def seletor_de_datas(selecionada):
        """Os próximos dias, para o usuário trocar de data com um clique."""
        primeiro = agora().replace(hour=0, minute=0, second=0, microsecond=0)
        dias = []
        for i in range(DIAS_NO_SELETOR):
            dia = primeiro + timedelta(days=i)
            iso = dia.strftime("%Y-%m-%d")
            dias.append(
                {
                    "iso": iso,
                    "semana": DIAS_DA_SEMANA[dia.weekday()],
                    "numero": dia.day,
                    "mes": MESES[dia.month - 1],
                    "selecionada": iso == selecionada,
                }
            )
        return dias

    def data_do_pedido():
        """Data pedida na URL; se vier vazia ou inválida, usa hoje."""
        data = request.args.get("data", "")
        return data if not regras.validar_formato(data, "00:00", "00:00") else hoje_iso()

    @app.route("/areas/<int:area_id>")
    def area(area_id):
        con = conexao()
        area = db.buscar_area(con, area_id)
        if area is None:
            con.close()
            abort(404)
        data = data_do_pedido()
        reservas_do_dia = db.listar_reservas(con, area_id=area_id, status=db.STATUS_CONFIRMADA, data=data)
        unidades = db.listar_unidades(con)
        con.close()

        inicio = request.args.get("inicio", "")
        fim = request.args.get("fim", "")
        if inicio and not fim and not regras.validar_formato(data, inicio, "00:00"):
            fim = regras.para_hhmm(min(regras.para_minutos(inicio) + 60, regras.para_minutos(area["fecha"])))

        limite = agora() + timedelta(days=regras.DIAS_MAX_ANTECEDENCIA)
        return render_template(
            "area.html",
            area=area,
            data=data,
            datas=seletor_de_datas(data),
            faixas=regras.linha_do_tempo(area, reservas_do_dia),
            unidades=unidades,
            inicio=inicio,
            fim=fim,
            unidade_escolhida=request.args.get("unidade", type=int),
            observacao=request.args.get("observacao", ""),
            hoje=hoje_iso(),
            limite=limite.strftime("%Y-%m-%d"),
            max_reservas_mes=regras.LIMITE_RESERVAS_MES_POR_UNIDADE,
            max_dias=regras.DIAS_MAX_ANTECEDENCIA,
            horas_cancelamento=regras.HORAS_MIN_CANCELAMENTO,
        )

    @app.route("/reservar", methods=["POST"])
    def reservar():
        form = request.form
        area_id = form.get("area_id", type=int)
        unidade_id = form.get("unidade_id", type=int)
        data, inicio, fim = form.get("data", ""), form.get("inicio", ""), form.get("fim", "")
        observacao = form.get("observacao", "")

        if area_id is None:
            abort(400)

        con = conexao()
        reserva_id, erros = servicos.reservar(con, area_id, unidade_id, data, inicio, fim, agora(), observacao)
        con.close()

        if erros:
            for erro in erros:
                flash(erro, "erro")
            # volta para a mesma tela com o formulário preenchido, para a pessoa só corrigir o que faltou
            return redirect(
                url_for("area", area_id=area_id, data=data, inicio=inicio, fim=fim, unidade=unidade_id, observacao=observacao)
            )
        flash(f"Reserva confirmada para {formatar_data(data)}, das {inicio} às {fim}.", "ok")
        return redirect(url_for("area", area_id=area_id, data=data))

    return app


app = criar_app()

if __name__ == "__main__":
    _con = db.conectar()
    seed.carregar_dados_ficticios(_con)  # só age se o banco estiver vazio
    _con.close()
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")
