import sqlite3

import pytest

from condominio import db


@pytest.fixture
def conexao():
    return db.conectar(":memory:")


@pytest.fixture
def salao(conexao):
    return db.adicionar_area(conexao, "Salão de festas", "Com cozinha", 60, "09:00", "23:00", 6, 48)


@pytest.fixture
def unidade(conexao):
    return db.adicionar_unidade(conexao, "A", "101", "Família Almeida")


def test_adicionar_e_buscar_area(conexao, salao):
    area = db.buscar_area(conexao, salao)
    assert (area["nome"], area["capacidade"], area["abre"], area["fecha"]) == ("Salão de festas", 60, "09:00", "23:00")
    assert db.buscar_area(conexao, 999) is None


def test_nome_da_area_e_unico(conexao, salao):
    with pytest.raises(sqlite3.IntegrityError):
        db.adicionar_area(conexao, "Salão de festas", "", 10, "09:00", "22:00", 2, 0)


def test_unidade_repetida_nao_e_permitida(conexao, unidade):
    with pytest.raises(sqlite3.IntegrityError):
        db.adicionar_unidade(conexao, "A", "101", "Outra pessoa")
    assert len(db.listar_unidades(conexao)) == 1


def test_listar_unidades_ordenadas(conexao):
    db.adicionar_unidade(conexao, "B", "101", "X")
    db.adicionar_unidade(conexao, "A", "202", "Y")
    db.adicionar_unidade(conexao, "A", "101", "Z")
    assert [(u["bloco"], u["numero"]) for u in db.listar_unidades(conexao)] == [("A", "101"), ("A", "202"), ("B", "101")]


def test_inserir_e_buscar_reserva_com_nomes(conexao, salao, unidade):
    rid = db.inserir_reserva(conexao, salao, unidade, "2026-11-10", "18:00", "22:00", "2026-10-27T10:00", "Aniversário")
    conexao.commit()
    reserva = db.buscar_reserva(conexao, rid)
    assert reserva["area_nome"] == "Salão de festas"
    assert (reserva["bloco"], reserva["numero"], reserva["morador"]) == ("A", "101", "Família Almeida")
    assert reserva["status"] == "confirmada"
    assert reserva["observacao"] == "Aniversário"


def test_reserva_exige_area_e_unidade_existentes(conexao):
    with pytest.raises(sqlite3.IntegrityError):
        db.inserir_reserva(conexao, 999, 999, "2026-11-10", "18:00", "20:00", "2026-10-27T10:00")


def test_listar_reservas_filtra_e_ordena(conexao, salao, unidade):
    churras = db.adicionar_area(conexao, "Churrasqueira", "", 20, "10:00", "22:00", 5, 24)
    db.inserir_reserva(conexao, salao, unidade, "2026-11-12", "10:00", "12:00", "x")
    db.inserir_reserva(conexao, salao, unidade, "2026-11-10", "18:00", "20:00", "x")
    db.inserir_reserva(conexao, churras, unidade, "2026-11-11", "12:00", "14:00", "x")
    conexao.commit()

    todas = db.listar_reservas(conexao)
    assert [r["data"] for r in todas] == ["2026-11-10", "2026-11-11", "2026-11-12"]
    assert len(db.listar_reservas(conexao, area_id=salao)) == 2
    assert [r["area_nome"] for r in db.listar_reservas(conexao, data="2026-11-11")] == ["Churrasqueira"]
    assert [r["data"] for r in db.listar_reservas(conexao, a_partir_de="2026-11-11")] == ["2026-11-11", "2026-11-12"]


def test_cancelar_reserva(conexao, salao, unidade):
    rid = db.inserir_reserva(conexao, salao, unidade, "2026-11-10", "18:00", "20:00", "x")
    conexao.commit()
    assert db.cancelar_reserva(conexao, rid, "2026-10-28T09:00") is True
    reserva = db.buscar_reserva(conexao, rid)
    assert reserva["status"] == "cancelada" and reserva["cancelada_em"] == "2026-10-28T09:00"
    assert db.cancelar_reserva(conexao, rid, "2026-10-28T10:00") is False  # já estava cancelada
    assert db.cancelar_reserva(conexao, 999, "x") is False


def test_contar_reservas_da_unidade_no_mes_ignora_canceladas(conexao, salao, unidade):
    a = db.inserir_reserva(conexao, salao, unidade, "2026-11-10", "10:00", "12:00", "x")
    db.inserir_reserva(conexao, salao, unidade, "2026-11-20", "10:00", "12:00", "x")
    db.inserir_reserva(conexao, salao, unidade, "2026-12-01", "10:00", "12:00", "x")
    conexao.commit()
    assert db.contar_reservas_da_unidade_no_mes(conexao, unidade, "2026-11") == 2
    db.cancelar_reserva(conexao, a, "x")
    assert db.contar_reservas_da_unidade_no_mes(conexao, unidade, "2026-11") == 1
