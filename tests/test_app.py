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


# --- página da área e reservas -------------------------------------------

def id_da_area(tmp_path, nome):
    con = db.conectar(tmp_path / "teste.db")
    return next(a["id"] for a in db.listar_areas(con) if a["nome"] == nome)


def test_pagina_da_area_mostra_a_linha_do_tempo(client, tmp_path):
    salao = id_da_area(tmp_path, "Salão de festas")
    html = client.get(f"/areas/{salao}?data=2026-10-30").get_data(as_text=True)  # reserva do exemplo: qui 30, 18:00-22:00
    assert "Salão de festas" in html
    assert html.count("faixa ocupada") == 4  # 18h, 19h, 20h e 21h
    assert "Reservado · Bloco A, apto 101" in html
    assert "09:00" in html and "22:00" in html


def test_horario_livre_leva_ao_formulario_preenchido(client, tmp_path):
    salao = id_da_area(tmp_path, "Salão de festas")
    html = client.get(f"/areas/{salao}?data=2026-11-05&inicio=14:00&fim=15:00").get_data(as_text=True)
    assert 'name="inicio" value="14:00"' in html
    assert 'name="fim" value="15:00"' in html
    assert 'name="data" value="2026-11-05"' in html


def test_fim_padrao_e_uma_hora_depois_do_inicio(client, tmp_path):
    salao = id_da_area(tmp_path, "Salão de festas")
    html = client.get(f"/areas/{salao}?data=2026-11-05&inicio=14:00").get_data(as_text=True)
    assert 'name="fim" value="15:00"' in html


def test_data_invalida_cai_em_hoje(client, tmp_path):
    salao = id_da_area(tmp_path, "Salão de festas")
    html = client.get(f"/areas/{salao}?data=lixo").get_data(as_text=True)
    assert 'name="data" value="2026-10-27"' in html


def test_area_inexistente_da_404(client):
    assert client.get("/areas/999").status_code == 404


def test_seletor_mostra_14_dias(client, tmp_path):
    salao = id_da_area(tmp_path, "Salão de festas")
    html = client.get(f"/areas/{salao}").get_data(as_text=True)
    assert html.count("<strong>") >= 14
    assert 'aria-current="date"' in html


def dados_da_reserva(tmp_path, **mudancas):
    con = db.conectar(tmp_path / "teste.db")
    salao = next(a["id"] for a in db.listar_areas(con) if a["nome"] == "Salão de festas")
    unidade = db.listar_unidades(con)[3]["id"]  # A 202: sem reservas de exemplo no salão
    dados = {"area_id": salao, "unidade_id": unidade, "data": "2026-11-20", "inicio": "14:00", "fim": "18:00", "observacao": "Teste"}
    dados.update(mudancas)
    return dados


def test_reservar_com_sucesso(client, tmp_path):
    dados = dados_da_reserva(tmp_path)
    resposta = client.post("/reservar", data=dados, follow_redirects=True)
    html = resposta.get_data(as_text=True)
    assert "Reserva confirmada para sex, 20 nov, das 14:00 às 18:00." in html
    assert "Reservado · Bloco A, apto 202" in html


def test_reservar_com_conflito_mostra_o_motivo_e_mantem_o_formulario(client, tmp_path):
    dados = dados_da_reserva(tmp_path, data="2026-10-30", inicio="19:00", fim="21:00")  # conflita com A 101 (18-22)
    html = client.post("/reservar", data=dados, follow_redirects=True).get_data(as_text=True)
    assert "Já existe uma reserva neste horário, das 18:00 às 22:00." in html
    assert 'name="inicio" value="19:00"' in html
    assert 'name="observacao" value="Teste"' in html


def test_reservar_mostra_todos_os_motivos_de_uma_vez(client, tmp_path):
    dados = dados_da_reserva(tmp_path, data="2026-10-27", inicio="07:00", fim="20:00")
    html = client.post("/reservar", data=dados, follow_redirects=True).get_data(as_text=True)
    assert "funciona das 09:00 às 23:00" in html
    assert "duração máxima" in html
    assert "já passou" in html or "antecedência" in html


def test_reservar_sem_area_da_400(client, tmp_path):
    assert client.post("/reservar", data={"unidade_id": 1}).status_code == 400


# --- lista de reservas e cancelamento ------------------------------------

def test_lista_mostra_as_reservas_futuras_confirmadas(client):
    html = client.get("/reservas").get_data(as_text=True)
    assert "Aniversário de 8 anos" in html
    assert "Família Almeida" in html
    assert html.count("<tr") == 1 + len(seed.RESERVAS_DE_EXEMPLO) + len(seed.RESERVAS_DE_HOJE)  # cabeçalho + linhas


def test_filtrar_por_area_e_unidade(client, tmp_path):
    salao = id_da_area(tmp_path, "Salão de festas")
    html = client.get(f"/reservas?area={salao}").get_data(as_text=True)
    assert html.count("<tr") == 1 + 2  # cabeçalho + as duas reservas do salão
    assert "Churrasqueira</td>" not in html

    con = db.conectar(tmp_path / "teste.db")
    a101 = db.listar_unidades(con)[0]["id"]
    html = client.get(f"/reservas?unidade={a101}").get_data(as_text=True)
    assert html.count("<tr") == 1 + 1  # só o aniversário da A 101


def test_filtro_de_situacao_invalido_volta_ao_padrao(client):
    assert client.get("/reservas?status=lixo").status_code == 200


def test_cancelar_reserva_pela_tela(client, tmp_path):
    con = db.conectar(tmp_path / "teste.db")
    aniversario = next(r for r in db.listar_reservas(con) if r["observacao"] == "Aniversário de 8 anos")  # em 3 dias
    resposta = client.post(f"/reservas/{aniversario['id']}/cancelar", follow_redirects=True)
    assert "Reserva cancelada. O horário voltou a ficar livre." in resposta.get_data(as_text=True)
    assert db.buscar_reserva(con, aniversario["id"])["status"] == "cancelada"
    assert "Aniversário de 8 anos" not in client.get("/reservas").get_data(as_text=True)  # saiu da lista de confirmadas
    assert "Aniversário de 8 anos" in client.get("/reservas?status=cancelada").get_data(as_text=True)


def test_nao_cancela_fora_do_prazo(client, tmp_path):
    con = db.conectar(tmp_path / "teste.db")
    de_hoje = next(r for r in db.listar_reservas(con) if r["data"] == "2026-10-27")  # começa em poucas horas
    html = client.post(f"/reservas/{de_hoje['id']}/cancelar", follow_redirects=True).get_data(as_text=True)
    assert "24 horas de antecedência" in html
    assert db.buscar_reserva(con, de_hoje["id"])["status"] == "confirmada"


def test_botao_cancelar_so_aparece_quando_permitido(client):
    html = client.get("/reservas").get_data(as_text=True)
    assert "botao-texto" in html  # reservas distantes podem ser canceladas
    assert "Fora do prazo" in html  # as de hoje não


def test_cancelar_reserva_inexistente(client):
    html = client.post("/reservas/999/cancelar", follow_redirects=True).get_data(as_text=True)
    assert "Reserva não encontrada." in html


def test_cancelar_so_aceita_post(client):
    assert client.get("/reservas/1/cancelar").status_code == 405


# --- unidades ------------------------------------------------------------

def test_lista_de_unidades_mostra_o_uso_do_mes(client):
    html = client.get("/unidades").get_data(as_text=True)
    assert "Família Almeida" in html
    assert "1 de 3" in html  # A 101: uma reserva no mês
    assert html.count("<tr") == 1 + len(seed.UNIDADES)


def test_cadastrar_unidade(client):
    resposta = client.post("/unidades", data={"bloco": " c ", "numero": "301", "morador": "Família Nunes"}, follow_redirects=True)
    html = resposta.get_data(as_text=True)
    assert "Bloco C, apto 301 cadastrado." in html
    assert "Família Nunes" in html


def test_cadastrar_unidade_repetida(client):
    html = client.post("/unidades", data={"bloco": "A", "numero": "101", "morador": "Outra"}, follow_redirects=True).get_data(as_text=True)
    assert "Bloco A, apto 101 já está cadastrado." in html
    assert html.count("<tr") == 1 + len(seed.UNIDADES)


def test_cadastrar_unidade_incompleta_ou_grande_demais(client):
    html = client.post("/unidades", data={"bloco": "A", "numero": "", "morador": "X"}, follow_redirects=True).get_data(as_text=True)
    assert "Preencha o bloco" in html
    html = client.post("/unidades", data={"bloco": "A", "numero": "9", "morador": "X" * 81}, follow_redirects=True).get_data(as_text=True)
    assert "grande demais" in html
