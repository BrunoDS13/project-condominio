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
    return True


if __name__ == "__main__":
    conexao = db.conectar()
    print("Dados fictícios carregados." if carregar_dados_ficticios(conexao) else "O banco já tem dados. Nada foi alterado.")
