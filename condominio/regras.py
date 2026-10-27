"""Regras de negócio das reservas.

Tudo aqui são funções puras: recebem dados e devolvem o resultado, sem acessar banco
nem Flask. Isso deixa as regras fáceis de ler e de testar.
"""
from datetime import datetime, timedelta

DIAS_MAX_ANTECEDENCIA = 60
LIMITE_RESERVAS_MES_POR_UNIDADE = 3
HORAS_MIN_CANCELAMENTO = 24


def para_minutos(hhmm):
    """'18:30' -> 1110"""
    hora, minuto = hhmm.split(":")
    return int(hora) * 60 + int(minuto)


def para_hhmm(minutos):
    """1110 -> '18:30'"""
    return f"{minutos // 60:02d}:{minutos % 60:02d}"


def inicio_da_reserva(data, inicio):
    """Junta data ('AAAA-MM-DD') e hora ('HH:MM') em um datetime."""
    return datetime.strptime(f"{data} {inicio}", "%Y-%m-%d %H:%M")


def _horas(quantidade):
    return f"{quantidade} hora" if quantidade == 1 else f"{quantidade} horas"


def validar_formato(data, inicio, fim):
    """Confere se data e horários vieram no formato certo. Devolve a lista de erros (vazia se estiver tudo certo)."""
    erros = []
    try:
        datetime.strptime(data, "%Y-%m-%d")
    except (ValueError, TypeError):
        erros.append("Informe uma data válida.")
    for rotulo, valor in (("início", inicio), ("término", fim)):
        try:
            datetime.strptime(valor, "%H:%M")
        except (ValueError, TypeError):
            erros.append(f"Informe um horário de {rotulo} válido.")
    return erros


def validar_reserva(area, data, inicio, fim, agora, reservas_do_dia, total_da_unidade_no_mes):
    """Aplica as regras e devolve a lista de motivos pelos quais a reserva NÃO pode ser feita.

    Lista vazia significa que a reserva é válida. Presume que o formato já foi conferido
    (veja `validar_formato`).

    area: a área pedida (abre, fecha, duracao_max_horas, antecedencia_min_horas).
    reservas_do_dia: reservas dessa área nesse dia (só as confirmadas contam como conflito).
    total_da_unidade_no_mes: reservas confirmadas da unidade no mês da data pedida.
    """
    minutos_inicio, minutos_fim = para_minutos(inicio), para_minutos(fim)
    if minutos_fim <= minutos_inicio:
        return ["O horário de término deve ser depois do início."]

    erros = []

    if minutos_inicio < para_minutos(area["abre"]) or minutos_fim > para_minutos(area["fecha"]):
        erros.append(f"{area['nome']} funciona das {area['abre']} às {area['fecha']}.")

    duracao_max = area["duracao_max_horas"]
    if minutos_fim - minutos_inicio > duracao_max * 60:
        erros.append(f"A duração máxima nesta área é de {_horas(duracao_max)}.")

    comeco = inicio_da_reserva(data, inicio)
    antecedencia_min = area["antecedencia_min_horas"]
    if comeco <= agora:
        erros.append("Não é possível reservar um horário que já passou.")
    elif comeco - agora < timedelta(hours=antecedencia_min):
        erros.append(f"Reservas nesta área exigem {_horas(antecedencia_min)} de antecedência.")
    if comeco > agora + timedelta(days=DIAS_MAX_ANTECEDENCIA):
        erros.append(f"Só é possível reservar com até {DIAS_MAX_ANTECEDENCIA} dias de antecedência.")

    if total_da_unidade_no_mes >= LIMITE_RESERVAS_MES_POR_UNIDADE:
        erros.append(
            f"A unidade já tem {LIMITE_RESERVAS_MES_POR_UNIDADE} reservas confirmadas em {data[:7]}, que é o limite por mês."
        )

    for outra in reservas_do_dia:
        if outra["status"] != "confirmada":
            continue
        # dois intervalos se sobrepõem quando cada um começa antes de o outro terminar
        if minutos_inicio < para_minutos(outra["fim"]) and minutos_fim > para_minutos(outra["inicio"]):
            erros.append(f"Já existe uma reserva neste horário, das {outra['inicio']} às {outra['fim']}.")
            break

    return erros


def pode_cancelar(reserva, agora):
    """Devolve (pode, motivo). O motivo vem vazio quando o cancelamento é permitido."""
    if reserva["status"] != "confirmada":
        return False, "Esta reserva já foi cancelada."
    comeco = inicio_da_reserva(reserva["data"], reserva["inicio"])
    if comeco <= agora:
        return False, "Esta reserva já aconteceu ou está em andamento."
    if comeco - agora < timedelta(hours=HORAS_MIN_CANCELAMENTO):
        return False, f"Cancelamentos só são aceitos com {_horas(HORAS_MIN_CANCELAMENTO)} de antecedência."
    return True, ""


def linha_do_tempo(area, reservas_do_dia):
    """Divide o funcionamento da área em faixas de 1 hora e diz quais estão ocupadas.

    Devolve uma lista de dicionários: {'inicio': '09:00', 'fim': '10:00', 'reserva': <reserva ou None>}.
    """
    confirmadas = [r for r in reservas_do_dia if r["status"] == "confirmada"]
    abre, fecha = para_minutos(area["abre"]), para_minutos(area["fecha"])

    faixas = []
    for comeco in range(abre, fecha, 60):
        termino = min(comeco + 60, fecha)
        ocupada_por = next(
            (r for r in confirmadas if comeco < para_minutos(r["fim"]) and termino > para_minutos(r["inicio"])),
            None,
        )
        faixas.append({"inicio": para_hhmm(comeco), "fim": para_hhmm(termino), "reserva": ocupada_por})
    return faixas


def segmentos_do_dia(area, reservas_do_dia):
    """Calcula os trechos ocupados do dia como porcentagens da largura da barra (0 a 100).

    A barra vai da abertura ao fechamento da área. Devolve uma lista de dicionários:
    {'esquerda': 35.7, 'largura': 28.6, 'inicio': '14:00', 'fim': '18:00'}.
    """
    abre, fecha = para_minutos(area["abre"]), para_minutos(area["fecha"])
    total = fecha - abre
    segmentos = []
    for r in reservas_do_dia:
        if r["status"] != "confirmada":
            continue
        comeco, termino = max(para_minutos(r["inicio"]), abre), min(para_minutos(r["fim"]), fecha)
        if termino <= comeco:
            continue
        segmentos.append(
            {
                "esquerda": round((comeco - abre) / total * 100, 2),
                "largura": round((termino - comeco) / total * 100, 2),
                "inicio": r["inicio"],
                "fim": r["fim"],
            }
        )
    return segmentos
