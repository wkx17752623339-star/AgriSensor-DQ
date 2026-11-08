"""Persistent datasets and reproducible experiment records."""
from pathlib import Path
import json, sqlite3, hashlib
from datetime import datetime, timezone
import pandas as pd
from engine import normalize
from services.storage import DB, init
BASE=DB.parent

def setup():
    init()
    (BASE/'datasets').mkdir(parents=True,exist_ok=True)
    with sqlite3.connect(DB) as c:
        c.execute("CREATE TABLE IF NOT EXISTS datasets (id TEXT PRIMARY KEY, name TEXT, source TEXT, created TEXT, rows INTEGER, nodes INTEGER)")
        c.execute("CREATE TABLE IF NOT EXISTS runs (id INTEGER PRIMARY KEY AUTOINCREMENT, created TEXT, dataset_id TEXT, method TEXT, parameters TEXT, metrics TEXT)")

def save_dataset(df,name,source):
    setup();d=normalize(df)
    digest=hashlib.sha256(d.to_csv(index=False).encode('utf-8')).hexdigest()[:16]
    path=BASE/'datasets'/f'{digest}.csv'
    d.to_csv(path,index=False,encoding='utf-8-sig')
    with sqlite3.connect(DB) as c:
        c.execute('INSERT OR REPLACE INTO datasets VALUES (?,?,?,?,?,?)',(digest,str(name),str(source),datetime.now(timezone.utc).isoformat(),len(d),int(d.node_id.nunique())))
    return digest

def list_datasets():
    setup()
    with sqlite3.connect(DB) as c:return pd.read_sql_query('SELECT * FROM datasets ORDER BY created DESC',c)

def load_dataset(dataset_id):
    setup();path=BASE/'datasets'/f'{dataset_id}.csv'
    if not path.is_file():raise FileNotFoundError('数据集文件不存在')
    return normalize(pd.read_csv(path))

def save_run(dataset_id,method,parameters,metrics):
    setup()
    with sqlite3.connect(DB) as c:
        cur=c.execute('INSERT INTO runs(created,dataset_id,method,parameters,metrics) VALUES(?,?,?,?,?)',(datetime.now(timezone.utc).isoformat(),dataset_id,method,json.dumps(parameters,ensure_ascii=False),json.dumps(metrics,ensure_ascii=False)))
        return cur.lastrowid

def list_runs():
    setup()
    with sqlite3.connect(DB) as c:return pd.read_sql_query('SELECT * FROM runs ORDER BY id DESC',c)

# Persistent active dataset selection (independent of Streamlit session state).
def set_active_dataset(dataset_id):
    setup()
    # Verify the dataset can actually be restored before updating the pointer.
    load_dataset(dataset_id)
    with sqlite3.connect(DB) as c:
        c.execute('CREATE TABLE IF NOT EXISTS app_state (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
        c.execute('INSERT OR REPLACE INTO app_state(key,value) VALUES (?,?)', ('active_dataset_id', str(dataset_id)))


def get_active_dataset():
    setup()
    with sqlite3.connect(DB) as c:
        c.execute('CREATE TABLE IF NOT EXISTS app_state (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
        row = c.execute('SELECT value FROM app_state WHERE key=?', ('active_dataset_id',)).fetchone()
    return row[0] if row else None


def clear_active_dataset():
    setup()
    with sqlite3.connect(DB) as c:
        c.execute('CREATE TABLE IF NOT EXISTS app_state (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
        c.execute('DELETE FROM app_state WHERE key=?', ('active_dataset_id',))
