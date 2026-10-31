# SEZIONE: Bacheca e persistenza delle assegnazioni
import sqlite3
from datetime import datetime
from .store import connect


def init_board():
    with connect() as db:
        db.execute('CREATE TABLE IF NOT EXISTS assegnazioni (data TEXT NOT NULL, elemento TEXT NOT NULL, tecnico_id TEXT NOT NULL, PRIMARY KEY(data,elemento))')
        db.execute('CREATE TABLE IF NOT EXISTS impegni (id TEXT PRIMARY KEY, data TEXT NOT NULL, tecnico_id TEXT NOT NULL, categoria TEXT NOT NULL, descrizione TEXT NOT NULL, indirizzo TEXT NOT NULL, fascia_inizio TEXT NOT NULL, fascia_fine TEXT NOT NULL, durata_min INTEGER NOT NULL, motivazione TEXT NOT NULL)')


def get_assignments(day):
    init_board()
    with connect() as db:
        return {key: tech for key, tech in db.execute('SELECT elemento, tecnico_id FROM assegnazioni WHERE data=?', (day,))}


def save_assignments(day, assignments):
    init_board()
    with connect() as db:
        db.execute('DELETE FROM assegnazioni WHERE data=?', (day,))
        db.executemany('INSERT INTO assegnazioni(data,elemento,tecnico_id) VALUES(?,?,?)', [(day,key,tech) for key,tech in assignments.items()])


def extras(day):
    init_board()
    with connect() as db:
        db.row_factory=sqlite3.Row
        return [dict(x) for x in db.execute('SELECT * FROM impegni WHERE data=? ORDER BY fascia_inizio,id', (day,))]


def add_extra(day, tech, category, description, address, start, end, duration, reason):
    init_board()
    key='extra_'+datetime.now().strftime('%Y%m%d%H%M%S%f')
    with connect() as db:
        db.execute('INSERT INTO impegni VALUES (?,?,?,?,?,?,?,?,?,?)', (key,day,tech,category,description,address,start,end,int(duration),reason))
    return key


def remove_extra(key):
    init_board()
    with connect() as db:
        db.execute('DELETE FROM impegni WHERE id=?', (key,))
        db.execute('DELETE FROM assegnazioni WHERE elemento=?', (key,))

# SEZIONE: Vincoli manuali e assegnazione progressiva

def get_manual(day):
    init_board()
    with connect() as db:
        db.execute('CREATE TABLE IF NOT EXISTS assegnazioni_manuali (data TEXT NOT NULL, elemento TEXT NOT NULL, tecnico_id TEXT NOT NULL, PRIMARY KEY(data,elemento))')
        return {key: tech for key,tech in db.execute('SELECT elemento,tecnico_id FROM assegnazioni_manuali WHERE data=?',(day,))}


def set_manual(day, key, tech):
    get_manual(day)
    with connect() as db:
        db.execute('INSERT OR REPLACE INTO assegnazioni_manuali VALUES(?,?,?)',(day,key,tech))


def clear_manual(day, key):
    get_manual(day)
    with connect() as db:
        db.execute('DELETE FROM assegnazioni_manuali WHERE data=? AND elemento=?',(day,key))


def plan_progressively(day, selected, progress=None):
    from .store import read
    from .geo import coordinate, matrix, minutes
    tech=read('tecnici'); tech=tech[tech.tecnico_id.astype(str).isin([str(x) for x in selected])]
    jobs=read('interventi'); jobs=jobs[jobs.data==day]
    clients=read('clienti').drop_duplicates('cliente_id').set_index('cliente_id')
    manual=get_manual(day)
    assignments={}
    timeline={str(t.tecnico_id):[] for _,t in tech.iterrows()}
    roster={str(t.tecnico_id):t for _,t in tech.iterrows()}
    pending=[]; rejected=[]
    for _,job in jobs.iterrows():
        key='job:'+str(job.intervento_id)
        if job.cliente_id not in clients.index:
            rejected.append(f'{job.intervento_id}: cliente inesistente');continue
        c=clients.loc[job.cliente_id]
        entry={'key':key,'job':job,'address':str(c.indirizzo),'lat':c.lat,'lon':c.lon,'start':minutes(job.fascia_inizio),'end':minutes(job.fascia_fine),'duration':int(float(job.durata_min))}
        tid=manual.get(key)
        if tid is not None:
            if tid and tid in roster:
                assignments[key]=tid;timeline[tid].append(entry)
                if str(roster[tid].ruolo)!=str(job.tipo):rejected.append(f'{key}: competenza tecnico incompatibile')
            else:
                assignments[key]=''
                if tid:rejected.append(f'{key}: tecnico vincolato assente')
        else:pending.append(entry)
    for _,w in read('magazzino').query('data == @day').iterrows():
        tid=str(w.tecnico_id)
        if tid in timeline:
            timeline[tid].append({'key':'warehouse:'+str(w.ritiro_id),'address':str(w.indirizzo),'lat':w.lat,'lon':w.lon,'start':minutes(w.fascia_inizio),'end':minutes(w.fascia_fine),'duration':int(float(w.durata_min))})
    for e in extras(day):
        tid=str(e['tecnico_id'])
        if tid in timeline and e['indirizzo']:
            timeline[tid].append({'key':e['id'],'address':e['indirizzo'],'lat':'','lon':'','start':minutes(e['fascia_inizio']),'end':minutes(e['fascia_fine']),'duration':int(e['durata_min'])})
    if not pending:
        assignments.update({e['key']:tid for tid,items in timeline.items() for e in items if not e['key'].startswith('job:')})
        save_assignments(day,assignments)
        return assignments,rejected
    if progress:progress('Localizzazione degli indirizzi e calcolo matrice stradale...')
    addresses=[]
    for t in roster.values():addresses.append((str(t.indirizzo_partenza),t.lat,t.lon))
    for items in timeline.values():
        for e in items:
            if e['address']:addresses.append((e['address'],e['lat'],e['lon']))
    for e in pending:addresses.append((e['address'],e['lat'],e['lon']))
    addresses=list(dict.fromkeys(addresses))
    locations={a:coordinate(*a) for a in addresses}
    points=list(dict.fromkeys(locations.values()))
    km,travel,_=matrix(points)
    index={p:i for i,p in enumerate(points)}
    def loc(e):return index[locations[(e['address'],e['lat'],e['lon'])]]
    def check(tid, items):
        t=roster[tid];pos=loc({'address':str(t.indirizzo_partenza),'lat':t.lat,'lon':t.lon})
        now=minutes(t.inizio);total_km=0
        for e in sorted(items,key=lambda x:(x['start'],x['end'])):
            nxt=loc(e);now+=travel[pos][nxt];total_km+=km[pos][nxt]
            now=max(now,e['start'])
            if now+e['duration']>e['end'] or now+e['duration']>minutes(t.fine):return None
            now+=e['duration'];pos=nxt
        end=loc({'address':str(t.indirizzo_partenza),'lat':t.lat,'lon':t.lon})
        if now+travel[pos][end]>minutes(t.fine):return None
        return total_km+km[pos][end]
    priorities={'Urgente':0,'Alta':1,'Normale':2,'Bassa':3}
    pending.sort(key=lambda e:(priorities.get(str(e['job'].priorita),2),e['start'],e['key']))
    for e in pending:
        candidates=[]
        for tid,t in roster.items():
            if str(t.ruolo)!=str(e['job'].tipo):continue
            new=check(tid,timeline[tid]+[e])
            if new is not None:
                old=check(tid,timeline[tid])
                candidates.append((new-(old or 0),new,tid))
        if candidates:
            _,_,tid=min(candidates);timeline[tid].append(e);assignments[e['key']]=tid
        else:assignments[e['key']]='';rejected.append(f'{e["key"]}: fascia oraria o trasferimento incompatibile')
    for tid,items in timeline.items():
        for e in items:assignments.setdefault(e['key'],tid)
    save_assignments(day,assignments)
    return assignments,rejected
