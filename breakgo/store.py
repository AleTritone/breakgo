# SEZIONE: Persistenza SQLite
import os
import sqlite3
import pandas as pd
from .schema import TABLES, KEYS

DB_PATH = os.environ.get('BREAKGO_DB', os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'breakgo.sqlite3'))

def connect():
    os.makedirs(os.path.dirname(os.path.abspath(DB_PATH)), exist_ok=True)
    return sqlite3.connect(DB_PATH, timeout=30)

def initialize():
    with connect() as db:
        for table, cols in TABLES.items():
            definitions = ', '.join('"%s" TEXT' % c for c in cols)
            db.execute(f'CREATE TABLE IF NOT EXISTS "{table}" ({definitions})')
        db.execute('CREATE TABLE IF NOT EXISTS soluzioni (data TEXT PRIMARY KEY, payload TEXT NOT NULL, creato TEXT NOT NULL)')

def read(table):
    with connect() as db:
        return pd.read_sql_query(f'SELECT * FROM "{table}"', db).fillna('')

def replace(table, df):
    cols = TABLES[table]
    data = df.reindex(columns=cols).fillna('').astype(str)
    with connect() as db:
        db.execute(f'DELETE FROM "{table}"')
        if len(data):
            data.to_sql(table, db, if_exists='append', index=False)

def validate(table, df):
    cols = TABLES[table]
    missing = set(cols) - set(df.columns)
    if missing:
        raise ValueError('Colonne mancanti: ' + ', '.join(sorted(missing)))
    clean = df[cols].fillna('').astype(str).apply(lambda c: c.str.strip())
    clean = clean.loc[~clean.eq('').all(axis=1)].reset_index(drop=True)
    if table in KEYS:
        key = KEYS[table]
        if clean[key].eq('').any() or clean[key].duplicated().any():
            raise ValueError(f'{key} obbligatorio e univoco')
    if table == 'presenze' and clean[['data','tecnico_id']].duplicated().any():
        raise ValueError('Presenza duplicata per tecnico e data')
    if table == 'tecnici':
        if not clean['ruolo'].isin(['Rifornimento','Manutenzione']).all():
            raise ValueError('Ruolo tecnico non valido')
        known = set(read('flotta')['mezzo_id'])
        if not set(clean['mezzo_id']) - {''} <= known:
            raise ValueError('Uno o più mezzi non sono presenti in Flotta')
    if table == 'interventi':
        if not clean['tipo'].isin(['Rifornimento','Manutenzione']).all():
            raise ValueError('Tipo intervento non valido')
        if not set(clean['cliente_id']) <= set(read('clienti')['cliente_id']):
            raise ValueError('Uno o più clienti non sono presenti in Clienti')
    if table in ('presenze','magazzino'):
        if not set(clean['tecnico_id']) <= set(read('tecnici')['tecnico_id']):
            raise ValueError('Uno o più tecnici non sono registrati')
    if table in ('interventi','magazzino'):
        for c in ('durata_min',):
            if (pd.to_numeric(clean[c], errors='coerce').isna() | (pd.to_numeric(clean[c], errors='coerce') < 0)).any():
                raise ValueError(f'{c} deve essere un numero non negativo')
    for c in ('data',):
        if c in clean and len(clean):
            if pd.to_datetime(clean[c], errors='coerce').isna().any():
                raise ValueError('Formato data non valido, utilizzare AAAA-MM-GG')
            clean[c] = pd.to_datetime(clean[c]).dt.strftime('%Y-%m-%d')
    return clean

def save_solution(day, payload):
    import json
    from datetime import datetime
    with connect() as db:
        db.execute('INSERT OR REPLACE INTO soluzioni VALUES (?,?,?)', (day, json.dumps(payload, ensure_ascii=False), datetime.now().isoformat(timespec='seconds')))

def load_solution(day):
    import json
    with connect() as db:
        row = db.execute('SELECT payload FROM soluzioni WHERE data=?', (day,)).fetchone()
    return json.loads(row[0]) if row else None
