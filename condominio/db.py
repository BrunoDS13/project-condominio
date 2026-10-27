import sqlite3
from pathlib import Path

CAMINHO_PADRAO = Path("condominio.db")

STATUS_CONFIRMADA = "confirmada"
STATUS_CANCELADA = "cancelada"


def conectar(caminho=CAMINHO_PADRAO):
    """Abre a conexão com o banco. Use ':memory:' nos testes."""
    conexao = sqlite3.connect(caminho)
    conexao.row_factory = sqlite3.Row
    conexao.execute("PRAGMA foreign_keys = ON")
    criar_tabelas(conexao)
    return conexao


def criar_tabelas(conexao):
    conexao.executescript(
        """
        CREATE TABLE IF NOT EXISTS areas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL UNIQUE,
            descricao TEXT NOT NULL DEFAULT '',
            capacidade INTEGER NOT NULL CHECK (capacidade > 0),
            abre TEXT NOT NULL,
            fecha TEXT NOT NULL,
            duracao_max_horas INTEGER NOT NULL CHECK (duracao_max_horas > 0),
            antecedencia_min_horas INTEGER NOT NULL CHECK (antecedencia_min_horas >= 0)
        );

        CREATE TABLE IF NOT EXISTS unidades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bloco TEXT NOT NULL,
            numero TEXT NOT NULL,
            morador TEXT NOT NULL,
            UNIQUE (bloco, numero)
        );

        CREATE TABLE IF NOT EXISTS reservas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            area_id INTEGER NOT NULL REFERENCES areas (id),
            unidade_id INTEGER NOT NULL REFERENCES unidades (id),
            data TEXT NOT NULL,
            inicio TEXT NOT NULL,
            fim TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'confirmada' CHECK (status IN ('confirmada', 'cancelada')),
            observacao TEXT NOT NULL DEFAULT '',
            criada_em TEXT NOT NULL,
            cancelada_em TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_reservas_area_data ON reservas (area_id, data);
        """
    )
    conexao.commit()


# --- áreas ---------------------------------------------------------------

def adicionar_area(conexao, nome, descricao, capacidade, abre, fecha, duracao_max_horas, antecedencia_min_horas):
    cursor = conexao.execute(
        "INSERT INTO areas (nome, descricao, capacidade, abre, fecha, duracao_max_horas, antecedencia_min_horas) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (nome, descricao, capacidade, abre, fecha, duracao_max_horas, antecedencia_min_horas),
    )
    conexao.commit()
    return cursor.lastrowid


def listar_areas(conexao):
    return conexao.execute("SELECT * FROM areas ORDER BY nome").fetchall()


def buscar_area(conexao, area_id):
    return conexao.execute("SELECT * FROM areas WHERE id = ?", (area_id,)).fetchone()


# --- unidades ------------------------------------------------------------

def adicionar_unidade(conexao, bloco, numero, morador):
    """Cadastra uma unidade. Levanta sqlite3.IntegrityError se bloco e número já existirem."""
    cursor = conexao.execute(
        "INSERT INTO unidades (bloco, numero, morador) VALUES (?, ?, ?)", (bloco, numero, morador)
    )
    conexao.commit()
    return cursor.lastrowid


def listar_unidades(conexao):
    return conexao.execute("SELECT * FROM unidades ORDER BY bloco, numero").fetchall()


def buscar_unidade(conexao, unidade_id):
    return conexao.execute("SELECT * FROM unidades WHERE id = ?", (unidade_id,)).fetchone()


# --- reservas ------------------------------------------------------------

_SELECT_RESERVAS = """
    SELECT r.*, a.nome AS area_nome, u.bloco, u.numero, u.morador
    FROM reservas r
    JOIN areas a ON a.id = r.area_id
    JOIN unidades u ON u.id = r.unidade_id
"""


def inserir_reserva(conexao, area_id, unidade_id, data, inicio, fim, criada_em, observacao=""):
    """Insere a reserva SEM confirmar a transação: quem chama decide quando fazer commit."""
    cursor = conexao.execute(
        "INSERT INTO reservas (area_id, unidade_id, data, inicio, fim, observacao, criada_em) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (area_id, unidade_id, data, inicio, fim, observacao, criada_em),
    )
    return cursor.lastrowid


def buscar_reserva(conexao, reserva_id):
    return conexao.execute(_SELECT_RESERVAS + " WHERE r.id = ?", (reserva_id,)).fetchone()


def listar_reservas(conexao, area_id=None, unidade_id=None, status=None, data=None, a_partir_de=None):
    """Lista reservas com área e unidade, da mais próxima para a mais distante. Todos os filtros são opcionais."""
    sql = _SELECT_RESERVAS + " WHERE 1 = 1"
    parametros = []
    for coluna, valor in (("r.area_id", area_id), ("r.unidade_id", unidade_id), ("r.status", status), ("r.data", data)):
        if valor:
            sql += f" AND {coluna} = ?"
            parametros.append(valor)
    if a_partir_de:
        sql += " AND r.data >= ?"
        parametros.append(a_partir_de)
    sql += " ORDER BY r.data, r.inicio, r.id"
    return conexao.execute(sql, parametros).fetchall()


def contar_reservas_da_unidade_no_mes(conexao, unidade_id, mes):
    """Conta as reservas confirmadas de uma unidade em um mês ('AAAA-MM')."""
    linha = conexao.execute(
        "SELECT COUNT(*) AS total FROM reservas WHERE unidade_id = ? AND status = 'confirmada' AND data LIKE ?",
        (unidade_id, f"{mes}%"),
    ).fetchone()
    return linha["total"]


def cancelar_reserva(conexao, reserva_id, cancelada_em):
    """Marca a reserva como cancelada. Devolve True se ela existia e ainda estava confirmada."""
    cursor = conexao.execute(
        "UPDATE reservas SET status = 'cancelada', cancelada_em = ? WHERE id = ? AND status = 'confirmada'",
        (cancelada_em, reserva_id),
    )
    conexao.commit()
    return cursor.rowcount > 0
