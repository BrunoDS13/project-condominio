from datetime import datetime

from condominio import regras

AGORA = datetime(2026, 10, 27, 10, 0)  # terça-feira

SALAO = {
    "nome": "Salão de festas",
    "abre": "09:00",
    "fecha": "23:00",
    "duracao_max_horas": 6,
    "antecedencia_min_horas": 48,
}
QUADRA = {"nome": "Quadra", "abre": "07:00", "fecha": "22:00", "duracao_max_horas": 2, "antecedencia_min_horas": 2}


def reserva(inicio, fim, status="confirmada", data="2026-11-10"):
    return {"data": data, "inicio": inicio, "fim": fim, "status": status}


def validar(area=SALAO, data="2026-11-10", inicio="18:00", fim="22:00", dia=(), no_mes=0, agora=AGORA):
    return regras.validar_reserva(area, data, inicio, fim, agora, list(dia), no_mes)


# --- conversões ----------------------------------------------------------

def test_conversao_de_horarios():
    assert regras.para_minutos("18:30") == 1110
    assert regras.para_hhmm(1110) == "18:30"
    assert regras.para_hhmm(540) == "09:00"


def test_validar_formato():
    assert regras.validar_formato("2026-11-10", "18:00", "22:00") == []
    assert regras.validar_formato("10/11/2026", "18:00", "22:00") == ["Informe uma data válida."]
    assert regras.validar_formato("2026-11-10", "25:00", "") == [
        "Informe um horário de início válido.",
        "Informe um horário de término válido.",
    ]
    assert regras.validar_formato(None, None, None) != []


# --- validação -----------------------------------------------------------

def test_reserva_valida_nao_tem_erros():
    assert validar() == []


def test_termino_deve_ser_depois_do_inicio():
    assert validar(inicio="20:00", fim="20:00") == ["O horário de término deve ser depois do início."]
    assert validar(inicio="20:00", fim="19:00") == ["O horário de término deve ser depois do início."]


def test_precisa_estar_dentro_do_funcionamento():
    assert "Salão de festas funciona das 09:00 às 23:00." in validar(inicio="08:00", fim="12:00")
    assert "Salão de festas funciona das 09:00 às 23:00." in validar(inicio="20:00", fim="23:30")
    assert validar(inicio="09:00", fim="15:00") == []  # encostar nos limites é permitido


def test_duracao_maxima():
    erros = validar(inicio="10:00", fim="17:00")
    assert "A duração máxima nesta área é de 6 horas." in erros
    assert validar(inicio="10:00", fim="16:00") == []
    assert "A duração máxima nesta área é de 2 horas." in validar(area=QUADRA, data="2026-11-10", inicio="10:00", fim="13:00")


def test_nao_reserva_horario_que_ja_passou():
    assert "Não é possível reservar um horário que já passou." in validar(data="2026-10-26")
    assert "Não é possível reservar um horário que já passou." in validar(data="2026-10-27", inicio="09:00", fim="11:00")


def test_antecedencia_minima():
    # salão exige 48h: agora é terça 10:00, então quinta 10:00 é o primeiro horário possível
    assert "Reservas nesta área exigem 48 horas de antecedência." in validar(data="2026-10-28")
    assert "Reservas nesta área exigem 48 horas de antecedência." in validar(data="2026-10-29", inicio="09:00", fim="12:00")
    assert validar(data="2026-10-29", inicio="10:00", fim="14:00") == []


def test_antecedencia_de_uma_hora_usa_singular():
    area = {**QUADRA, "antecedencia_min_horas": 1}
    assert "Reservas nesta área exigem 1 hora de antecedência." in validar(area=area, data="2026-10-27", inicio="10:30", fim="11:30")


def test_limite_maximo_de_dias():
    assert any("até 60 dias" in e for e in validar(data="2027-01-10"))
    assert validar(data="2026-12-20") == []


def test_limite_de_reservas_por_unidade_no_mes():
    assert validar(no_mes=2) == []
    erros = validar(no_mes=3)
    assert erros == ["A unidade já tem 3 reservas confirmadas em 2026-11, que é o limite por mês."]


def test_conflito_de_horario():
    existente = reserva("18:00", "22:00")
    assert validar(inicio="20:00", fim="23:00", dia=[existente]) == ["Já existe uma reserva neste horário, das 18:00 às 22:00."]
    assert validar(inicio="16:00", fim="19:00", dia=[existente]) != []  # sobrepõe o começo
    assert validar(inicio="19:00", fim="20:00", dia=[existente]) != []  # fica dentro
    assert validar(inicio="17:00", fim="23:00", dia=[existente]) != []  # engloba


def test_horarios_encostados_nao_sao_conflito():
    existente = reserva("18:00", "22:00")
    assert validar(inicio="14:00", fim="18:00", dia=[existente]) == []
    assert validar(inicio="22:00", fim="23:00", dia=[existente]) == []


def test_reserva_cancelada_nao_gera_conflito():
    assert validar(inicio="18:00", fim="22:00", dia=[reserva("18:00", "22:00", status="cancelada")]) == []


def test_varios_erros_sao_devolvidos_juntos():
    erros = validar(data="2026-10-26", inicio="07:00", fim="20:00", no_mes=3)
    assert len(erros) >= 4


# --- cancelamento --------------------------------------------------------

def test_pode_cancelar_com_antecedencia():
    assert regras.pode_cancelar(reserva("18:00", "22:00", data="2026-11-10"), AGORA) == (True, "")


def test_nao_cancela_em_cima_da_hora():
    pode, motivo = regras.pode_cancelar(reserva("09:00", "12:00", data="2026-10-28"), AGORA)  # faltam 23h
    assert pode is False and "24 horas de antecedência" in motivo
    assert regras.pode_cancelar(reserva("18:00", "22:00", data="2026-10-28"), AGORA)[0] is True  # faltam 32h
    assert regras.pode_cancelar(reserva("10:00", "12:00", data="2026-10-28"), AGORA)[0] is True  # exatamente 24h


def test_nao_cancela_reserva_passada_ou_ja_cancelada():
    assert regras.pode_cancelar(reserva("08:00", "09:00", data="2026-10-27"), AGORA) == (False, "Esta reserva já aconteceu ou está em andamento.")
    assert regras.pode_cancelar(reserva("18:00", "22:00", status="cancelada"), AGORA) == (False, "Esta reserva já foi cancelada.")


# --- linha do tempo ------------------------------------------------------

def test_linha_do_tempo_sem_reservas():
    faixas = regras.linha_do_tempo(QUADRA, [])
    assert len(faixas) == 15
    assert (faixas[0]["inicio"], faixas[0]["fim"]) == ("07:00", "08:00")
    assert (faixas[-1]["inicio"], faixas[-1]["fim"]) == ("21:00", "22:00")
    assert all(f["reserva"] is None for f in faixas)


def test_linha_do_tempo_marca_horas_ocupadas():
    r = reserva("18:00", "20:30")
    ocupadas = [f["inicio"] for f in regras.linha_do_tempo(SALAO, [r]) if f["reserva"]]
    assert ocupadas == ["18:00", "19:00", "20:00"]  # a faixa 20:00-21:00 está parcialmente ocupada


def test_linha_do_tempo_ignora_canceladas():
    assert all(f["reserva"] is None for f in regras.linha_do_tempo(SALAO, [reserva("18:00", "20:00", status="cancelada")]))


# --- barra do dia --------------------------------------------------------

def test_segmentos_do_dia_em_porcentagem():
    # quadra funciona 07:00-22:00 (900 min). 12:00-15:00 começa em 300 min (33,33%) e dura 180 min (20%)
    segmentos = regras.segmentos_do_dia(QUADRA, [reserva("12:00", "15:00")])
    assert segmentos == [{"esquerda": 33.33, "largura": 20.0, "inicio": "12:00", "fim": "15:00"}]


def test_segmentos_ignoram_canceladas_e_cortam_o_que_passa_do_funcionamento():
    segmentos = regras.segmentos_do_dia(QUADRA, [reserva("06:00", "08:00"), reserva("10:00", "11:00", status="cancelada")])
    assert len(segmentos) == 1
    assert segmentos[0]["esquerda"] == 0 and segmentos[0]["largura"] == 6.67  # só 07:00-08:00 cabe na barra


def test_segmentos_sem_reservas():
    assert regras.segmentos_do_dia(QUADRA, []) == []
