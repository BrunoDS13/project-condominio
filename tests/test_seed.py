from datetime import datetime

from condominio import db, seed

AGORA = datetime(2026, 10, 27, 10, 0)


def test_carrega_areas_unidades_e_reservas():
    conexao = db.conectar(":memory:")
    assert seed.carregar_dados_ficticios(conexao, AGORA) is True
    assert len(db.listar_areas(conexao)) == len(seed.AREAS)
    assert len(db.listar_unidades(conexao)) == len(seed.UNIDADES)
    reservas = db.listar_reservas(conexao)
    assert len(reservas) == len(seed.RESERVAS_DE_EXEMPLO)
    assert all(r["status"] == "confirmada" for r in reservas)


def test_reservas_de_exemplo_sao_sempre_no_futuro():
    conexao = db.conectar(":memory:")
    seed.carregar_dados_ficticios(conexao, AGORA)
    assert all(r["data"] > "2026-10-27" for r in db.listar_reservas(conexao))


def test_nao_duplica_dados_ao_rodar_de_novo():
    conexao = db.conectar(":memory:")
    seed.carregar_dados_ficticios(conexao, AGORA)
    assert seed.carregar_dados_ficticios(conexao, AGORA) is False
    assert len(db.listar_areas(conexao)) == len(seed.AREAS)
    assert len(db.listar_reservas(conexao)) == len(seed.RESERVAS_DE_EXEMPLO)


def test_funciona_em_qualquer_dia_do_ano():
    """As reservas são relativas a 'hoje', então precisam passar nas regras em qualquer data."""
    for mes in range(1, 13):
        conexao = db.conectar(":memory:")
        assert seed.carregar_dados_ficticios(conexao, datetime(2026, mes, 28, 10, 0)) is True
