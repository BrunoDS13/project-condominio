from datetime import datetime

import pytest

from condominio import db, servicos

AGORA = datetime(2026, 10, 27, 10, 0)


@pytest.fixture
def conexao(tmp_path):
    return db.conectar(tmp_path / "teste.db")


@pytest.fixture
def salao(conexao):
    return db.adicionar_area(conexao, "Salão de festas", "", 60, "09:00", "23:00", 6, 48)


@pytest.fixture
def unidade(conexao):
    return db.adicionar_unidade(conexao, "A", "101", "Família Almeida")


@pytest.fixture
def outra_unidade(conexao):
    return db.adicionar_unidade(conexao, "B", "202", "Família Barros")


def reservar(conexao, area, unidade, data="2026-11-10", inicio="18:00", fim="22:00", obs=""):
    return servicos.reservar(conexao, area, unidade, data, inicio, fim, AGORA, obs)


def test_reserva_valida_e_gravada(conexao, salao, unidade):
    reserva_id, erros = reservar(conexao, salao, unidade, obs="  Aniversário  ")
    assert erros == []
    reserva = db.buscar_reserva(conexao, reserva_id)
    assert (reserva["data"], reserva["inicio"], reserva["fim"], reserva["status"]) == ("2026-11-10", "18:00", "22:00", "confirmada")
    assert reserva["observacao"] == "Aniversário"
    assert reserva["criada_em"] == "2026-10-27T10:00"


def test_reserva_invalida_nao_grava_nada(conexao, salao, unidade):
    reserva_id, erros = reservar(conexao, salao, unidade, inicio="08:00", fim="12:00")
    assert reserva_id is None and erros
    assert db.listar_reservas(conexao) == []


def test_conflito_entre_unidades(conexao, salao, unidade, outra_unidade):
    assert reservar(conexao, salao, unidade)[1] == []
    reserva_id, erros = reservar(conexao, salao, outra_unidade, inicio="20:00", fim="23:00")
    assert reserva_id is None
    assert erros == ["Já existe uma reserva neste horário, das 18:00 às 22:00."]


def test_mesmo_horario_em_areas_diferentes_nao_conflita(conexao, salao, unidade, outra_unidade):
    churrasqueira = db.adicionar_area(conexao, "Churrasqueira", "", 20, "10:00", "22:00", 5, 24)
    assert reservar(conexao, salao, unidade)[1] == []
    assert reservar(conexao, churrasqueira, outra_unidade)[1] == []


def test_horario_cancelado_volta_a_ficar_livre(conexao, salao, unidade, outra_unidade):
    primeira, _ = reservar(conexao, salao, unidade)
    assert servicos.cancelar(conexao, primeira, AGORA) == (True, "")
    assert reservar(conexao, salao, outra_unidade)[1] == []


def test_limite_de_tres_reservas_por_mes(conexao, salao, unidade):
    for dia in ("2026-11-10", "2026-11-11", "2026-11-12"):
        assert reservar(conexao, salao, unidade, data=dia)[1] == []
    _, erros = reservar(conexao, salao, unidade, data="2026-11-13")
    assert any("limite por mês" in e for e in erros)
    assert reservar(conexao, salao, unidade, data="2026-12-01")[1] == []  # outro mês


def test_cancelar_reserva_ja_cancelada_ou_inexistente(conexao, salao, unidade):
    rid, _ = reservar(conexao, salao, unidade)
    servicos.cancelar(conexao, rid, AGORA)
    assert servicos.cancelar(conexao, rid, AGORA) == (False, "Esta reserva já foi cancelada.")
    assert servicos.cancelar(conexao, 999, AGORA) == (False, "Reserva não encontrada.")


def test_cancelar_em_cima_da_hora_e_recusado(conexao, salao, unidade):
    rid, erros = servicos.reservar(conexao, salao, unidade, "2026-10-29", "10:00", "12:00", AGORA)
    assert erros == []
    pode, motivo = servicos.cancelar(conexao, rid, datetime(2026, 10, 28, 12, 0))
    assert pode is False and "24 horas" in motivo
    assert db.buscar_reserva(conexao, rid)["status"] == "confirmada"


def test_entradas_invalidas(conexao, salao, unidade):
    assert reservar(conexao, 999, unidade)[1] == ["Escolha uma área válida."]
    assert reservar(conexao, salao, 999)[1] == ["Escolha uma unidade válida."]
    assert reservar(conexao, salao, unidade, data="lixo")[1] == ["Informe uma data válida."]


def test_segunda_conexao_enxerga_a_reserva_da_primeira(tmp_path, salao, unidade, outra_unidade):
    """Duas conexões independentes (como duas pessoas em abas diferentes), uma depois da outra."""
    caminho = tmp_path / "teste.db"
    primeira, segunda = db.conectar(caminho), db.conectar(caminho)
    assert servicos.reservar(primeira, salao, unidade, "2026-11-10", "18:00", "22:00", AGORA)[1] == []
    _, erros = servicos.reservar(segunda, salao, outra_unidade, "2026-11-10", "18:00", "22:00", AGORA)
    assert erros
    assert len(db.listar_reservas(primeira, status="confirmada")) == 1
