from datetime import datetime

from condominio import db, seed

AGORA = datetime(2026, 10, 27, 10, 0)


def test_carrega_areas_unidades_e_reservas():
    conexao = db.conectar(":memory:")
    assert seed.carregar_dados_ficticios(conexao, AGORA) is True
    assert len(db.listar_areas(conexao)) == len(seed.AREAS)
    assert len(db.listar_unidades(conexao)) == len(seed.UNIDADES)
    reservas = db.listar_reservas(conexao)
    assert len(reservas) == len(seed.RESERVAS_DE_EXEMPLO) + len(seed.RESERVAS_DE_HOJE)  # às 10:00 cabem todas as de hoje
    assert all(r["status"] == "confirmada" for r in reservas)


def test_reservas_de_exemplo_sao_sempre_no_futuro():
    conexao = db.conectar(":memory:")
    seed.carregar_dados_ficticios(conexao, AGORA)
    assert all(f"{r['data']} {r['inicio']}" > "2026-10-27 10:00" for r in db.listar_reservas(conexao))


def test_ha_reservas_hoje_para_a_barra_nao_ficar_vazia():
    conexao = db.conectar(":memory:")
    seed.carregar_dados_ficticios(conexao, AGORA)
    de_hoje = {r["area_nome"]: (r["inicio"], r["fim"]) for r in db.listar_reservas(conexao, data="2026-10-27")}
    assert de_hoje == {"Quadra poliesportiva": ("12:00", "14:00"), "Sala de estudos": ("11:00", "13:00")}


def test_sem_horario_hoje_nao_cria_reserva_de_hoje():
    conexao = db.conectar(":memory:")
    seed.carregar_dados_ficticios(conexao, datetime(2026, 10, 27, 21, 30))  # já é tarde demais
    assert db.listar_reservas(conexao, data="2026-10-27") == []


def test_nao_duplica_dados_ao_rodar_de_novo():
    conexao = db.conectar(":memory:")
    seed.carregar_dados_ficticios(conexao, AGORA)
    assert seed.carregar_dados_ficticios(conexao, AGORA) is False
    assert len(db.listar_areas(conexao)) == len(seed.AREAS)
    assert len(db.listar_reservas(conexao)) == len(seed.RESERVAS_DE_EXEMPLO) + len(seed.RESERVAS_DE_HOJE)


def test_funciona_em_qualquer_dia_do_ano():
    """As reservas são relativas a 'hoje', então precisam passar nas regras em qualquer data."""
    for mes in range(1, 13):
        for hora in (0, 7, 10, 15, 21, 23):
            conexao = db.conectar(":memory:")
            assert seed.carregar_dados_ficticios(conexao, datetime(2026, mes, 28, hora, 30)) is True
