"""Dados fictícios para demonstração. Nenhum nome ou unidade aqui existe de verdade."""
from datetime import datetime, timedelta

from condominio import db, servicos

AREAS = [
    # nome, descrição, capacidade, abre, fecha, duração máxima (h), antecedência mínima (h)
    ("Salão de festas", "Salão com cozinha equipada e som ambiente.", 60, "09:00", "23:00", 6, 48),
    ("Churrasqueira", "Espaço gourmet com churrasqueira e pia.", 20, "10:00", "22:00", 5, 24),
    ("Quadra poliesportiva", "Quadra coberta para futsal, vôlei e basquete.", 12, "07:00", "22:00", 2, 2),
    ("Sala de estudos", "Sala silenciosa com mesas e tomadas.", 8, "08:00", "22:00", 3, 1),
]

UNIDADES = [
    ("A", "101", "Família Almeida"),
    ("A", "102", "Família Barros"),
    ("A", "201", "Família Cardoso"),
    ("A", "202", "Família Duarte"),
    ("B", "101", "Família Esteves"),
    ("B", "102", "Família Farias"),
    ("B", "201", "Família Gouveia"),
    ("B", "202", "Família Hashimoto"),
]

# área, bloco, número, dias a partir de hoje, início, fim, observação
RESERVAS_DE_EXEMPLO = [
    ("Salão de festas", "A", "101", 3, "18:00", "22:00", "Aniversário de 8 anos"),
    ("Salão de festas", "B", "201", 10, "14:00", "20:00", "Confraternização da família"),
    ("Churrasqueira", "A", "202", 2, "12:00", "17:00", ""),
    ("Churrasqueira", "B", "102", 2, "18:00", "22:00", ""),
    ("Quadra poliesportiva", "B", "101", 1, "19:00", "21:00", "Futsal com amigos"),
    ("Quadra poliesportiva", "A", "102", 1, "21:00", "22:00", ""),
    ("Sala de estudos", "A", "201", 1, "14:00", "17:00", ""),
]


# Reservas de hoje, para a barra de disponibilidade não aparecer vazia na demonstração:
# área, bloco, número, duração em horas. O início é o primeiro horário cheio que a antecedência da área permite.
RESERVAS_DE_HOJE = [
    ("Quadra poliesportiva", "A", "202", 2),
    ("Sala de estudos", "B", "102", 2),
]


def _primeira_hora_cheia(agora, antecedencia_horas):
    """Primeiro horário cheio (HH:00) que respeita a antecedência mínima, a partir de agora."""
    limite = agora + timedelta(hours=antecedencia_horas)
    cheia = limite.replace(minute=0, second=0, microsecond=0)
    return cheia if cheia >= limite else cheia + timedelta(hours=1)


def carregar_dados_ficticios(conexao, agora=None):
    """Cadastra áreas, unidades e algumas reservas. Só age se o banco ainda não tiver áreas.

    Devolve True se carregou os dados, ou False se o banco já tinha conteúdo.
    """
    if db.listar_areas(conexao):
        return False
    agora = agora or datetime.now()

    ids_das_areas = {a[0]: db.adicionar_area(conexao, *a) for a in AREAS}
    ids_das_unidades = {(b, n): db.adicionar_unidade(conexao, b, n, m) for b, n, m in UNIDADES}

    for area, bloco, numero, dias, inicio, fim, observacao in RESERVAS_DE_EXEMPLO:
        data = (agora + timedelta(days=dias)).strftime("%Y-%m-%d")
        _, erros = servicos.reservar(
            conexao, ids_das_areas[area], ids_das_unidades[(bloco, numero)], data, inicio, fim, agora, observacao
        )
        if erros:  # os dados de exemplo precisam obedecer às mesmas regras do sistema
            raise ValueError(f"Reserva de exemplo inválida ({area}, {data}): {erros}")

    _reservar_para_hoje(conexao, agora, ids_das_areas, ids_das_unidades)
    return True


def _reservar_para_hoje(conexao, agora, ids_das_areas, ids_das_unidades):
    """Tenta criar reservas ainda hoje. Se não couber (já é tarde), simplesmente não cria."""
    antecedencias = {a[0]: a[6] for a in AREAS}
    for area, bloco, numero, horas in RESERVAS_DE_HOJE:
        comeco = _primeira_hora_cheia(agora, antecedencias[area])
        if comeco.date() != agora.date():
            continue
        fim = comeco + timedelta(hours=horas)
        servicos.reservar(
            conexao, ids_das_areas[area], ids_das_unidades[(bloco, numero)],
            comeco.strftime("%Y-%m-%d"), comeco.strftime("%H:%M"), fim.strftime("%H:%M"), agora,
        )  # erros (ex.: passa do horário de fechamento) são ignorados de propósito


if __name__ == "__main__":
    conexao = db.conectar()
    print("Dados fictícios carregados." if carregar_dados_ficticios(conexao) else "O banco já tem dados. Nada foi alterado.")
