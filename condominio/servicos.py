"""Casos de uso: juntam as regras (regras.py) com o banco (db.py)."""
from condominio import db, regras


def _agora_texto(agora):
    return agora.strftime("%Y-%m-%dT%H:%M")


def reservar(conexao, area_id, unidade_id, data, inicio, fim, agora, observacao=""):
    """Tenta criar uma reserva. Devolve (reserva_id, erros): se houver erros, o id é None e nada é gravado."""
    area = db.buscar_area(conexao, area_id)
    if area is None:
        return None, ["Escolha uma área válida."]
    if db.buscar_unidade(conexao, unidade_id) is None:
        return None, ["Escolha uma unidade válida."]

    erros = regras.validar_formato(data, inicio, fim)
    if erros:
        return None, erros

    # BEGIN IMMEDIATE trava o banco para escrita já aqui. Assim, a checagem de conflito e a
    # gravação acontecem sem que outra pessoa consiga reservar o mesmo horário no meio.
    conexao.execute("BEGIN IMMEDIATE")
    try:
        reservas_do_dia = db.listar_reservas(conexao, area_id=area_id, status=db.STATUS_CONFIRMADA, data=data)
        total_no_mes = db.contar_reservas_da_unidade_no_mes(conexao, unidade_id, data[:7])
        erros = regras.validar_reserva(area, data, inicio, fim, agora, reservas_do_dia, total_no_mes)
        if erros:
            conexao.rollback()
            return None, erros

        reserva_id = db.inserir_reserva(
            conexao, area_id, unidade_id, data, inicio, fim, _agora_texto(agora), observacao.strip()
        )
        conexao.commit()
        return reserva_id, []
    except Exception:
        conexao.rollback()
        raise


def cancelar(conexao, reserva_id, agora):
    """Cancela uma reserva se as regras permitirem. Devolve (cancelou, motivo)."""
    reserva = db.buscar_reserva(conexao, reserva_id)
    if reserva is None:
        return False, "Reserva não encontrada."

    pode, motivo = regras.pode_cancelar(reserva, agora)
    if not pode:
        return False, motivo

    db.cancelar_reserva(conexao, reserva_id, _agora_texto(agora))
    return True, ""
