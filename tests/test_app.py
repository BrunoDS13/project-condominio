from datetime import datetime

import pytest

from app import criar_app
from condominio import db, seed

AGORA = datetime(2026, 10, 27, 10, 0)  # terça-feira


def criar_cliente(caminho, com_dados=True, agora=AGORA):
    app = criar_app(caminho, agora=lambda: agora)
    app.config["TESTING"] = True
    if com_dados:
        con = db.conectar(caminho)
        seed.carregar_dados_ficticios(con, agora)
        con.close()
    return app.test_client()


@pytest.fixture
def client(tmp_path):
    return criar_cliente(tmp_path / "teste.db")


def test_pagina_inicial_lista_as_areas(client):
    resposta = client.get("/")
    assert resposta.status_code == 200
    html = resposta.get_data(as_text=True)
    for area in seed.AREAS:
        assert area[0] in html
    assert "Residencial Aurora" in html


def test_cartao_mostra_a_proxima_reserva(client):
    html = client.get("/").get_data(as_text=True)
    assert "Próxima reserva: qui, 29 out, 12:00" in html  # churrasqueira em +2 dias


def test_barra_do_dia_mostra_o_que_esta_ocupado_hoje(tmp_path):
    cliente = criar_cliente(tmp_path / "hoje.db", com_dados=False)
    con = db.conectar(tmp_path / "hoje.db")
    area = db.adicionar_area(con, "Quadra", "", 12, "08:00", "20:00", 2, 0)
    unidade = db.adicionar_unidade(con, "A", "101", "Família Teste")
    db.inserir_reserva(con, area, unidade, "2026-10-27", "14:00", "16:00", "x")  # hoje, depois do "agora" (10:00)
    con.commit()
    html = cliente.get("/").get_data(as_text=True)
    assert 'class="barra-ocupado"' in html
    assert "left: 50.0%" in html  # 14:00 fica na metade de 08:00-20:00


def test_area_sem_reservas_diz_isso(tmp_path):
    cliente = criar_cliente(tmp_path / "vazio.db", com_dados=False)
    con = db.conectar(tmp_path / "vazio.db")
    db.adicionar_area(con, "Quadra", "", 12, "08:00", "20:00", 2, 0)
    html = cliente.get("/").get_data(as_text=True)
    assert "Sem reservas marcadas" in html
    assert 'class="barra-ocupado"' not in html


def test_chave_secreta_vem_da_variavel_de_ambiente(tmp_path, monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "minha-chave-de-teste")
    assert criar_app(tmp_path / "a.db").config["SECRET_KEY"] == "minha-chave-de-teste"


def test_sem_variavel_a_chave_e_aleatoria(tmp_path, monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    assert criar_app(tmp_path / "a.db").config["SECRET_KEY"] != criar_app(tmp_path / "b.db").config["SECRET_KEY"]
