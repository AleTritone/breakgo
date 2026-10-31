# SEZIONE: Dati dimostrativi Break&Go distribuiti su Milano
from datetime import date
import pandas as pd
from .store import read, replace
from .milano_civici import CIVICI



# SEZIONE: Aziende fittizie e fasce orarie dimostrative
DEMO_NAMES = [
    'Navigli Digital S.r.l.', 'Lombarda Sistemi S.p.A.', 'Porta Nuova Consulting S.r.l.',
    'Aurora Design Studio', 'Milano Logistica Integrata', 'Brera Comunicazione S.r.l.',
    'Ticinese Servizi Aziendali', 'Bovisa Tech Lab', 'Isola Media Group',
    'Città Studi Engineering', 'Sempione Uffici S.r.l.', 'Lambrate Innovazione',
    'Portello Business Center', 'Darsena Architettura', 'Nord Ovest Componenti',
    'Ortica Creative Hub', 'Monforte Finanza S.r.l.', 'San Siro Medical Office',
    'Bicocca Data Solutions', 'Lorenteggio Elettronica', 'Vigentino Facility S.r.l.',
    'Porta Romana Partners', 'Certosa Mobility', 'Forlanini Healthcare',
    'Garibaldi Property S.r.l.', 'Corvetto Packaging', 'Niguarda Ricerca',
    'Famagosta Assicurazioni', 'Turro Energia S.r.l.', 'Precotto Industria',
    'Ripamonti Engineering', 'QT8 Sport Management', 'Affori Servizi S.r.l.',
    'Crescenzago Software', 'Gratosoglio Amministrazioni', 'Centrale Business S.r.l.',
    'Maciachini Office Group', 'Washington Retail Solutions', 'Udine Laboratori',
    'Pagano Hospitality S.r.l.', 'Bande Nere Consulting', 'Comasina Biomedical',
    'Rogoredo Facility Management', 'Missori Professional Services'
]
DEMO_SLOTS = [('08:00','09:30'),('09:00','10:30'),('10:00','11:30'),
              ('11:00','12:30'),('12:30','14:00'),('13:30','15:00'),
              ('14:30','16:00'),('15:30','17:00')]


def update_demo_records():
    clients=read('clienti'); jobs=read('interventi')
    renamed=0; scheduled=0
    for i,name in enumerate(DEMO_NAMES):
        cid=f'C{i+1:03d}'
        mask=clients['cliente_id'].eq(cid) & clients['ragione_sociale'].str.fullmatch(r'Punto ristoro\s+\d+',case=False,na=False)
        renamed+=int(mask.sum())
        clients.loc[mask,'ragione_sociale']=name
    for i in range(44):
        jid=f'I{i+1:03d}'
        mask=jobs['intervento_id'].eq(jid) & jobs['fascia_inizio'].isin(['08:00','08:30']) & jobs['fascia_fine'].eq('17:30')
        if mask.any():
            a,b=DEMO_SLOTS[i%len(DEMO_SLOTS)]
            jobs.loc[mask,'fascia_inizio']=a
            jobs.loc[mask,'fascia_fine']=b
            scheduled+=int(mask.sum())
    if renamed:replace('clienti',clients)
    if scheduled:replace('interventi',jobs)
    return renamed,scheduled

def seed(force=False):
    if not force and any(len(read(t)) for t in ('tecnici', 'flotta', 'clienti', 'interventi')):
        raise ValueError('Archivio non vuoto. Per preservare i dati usa Aggiorna indirizzi demo.')
    day = date.today().isoformat()
    names = [('T01','Andrea','Riva'),('T02','Luca','Ferrari'),('T03','Marco','Sala'),('T04','Davide','Conti'),('T05','Sara','Moretti')]
    vans, tech = [], []
    for i, (tid, nome, cognome) in enumerate(names):
        role = 'Rifornimento' if i < 4 else 'Manutenzione'
        van = f'F{i+1:02d}'
        vans.append([van,f'BG{i+101}GO','Fiat','Ducato' if i < 4 else 'Scudo',role,'si'])
        tech.append([tid,nome,cognome,role,van,'Via Giovanni Battista Pirelli 20, Milano','45.4852','9.2021','07:30','18:30','si'])
    clients, jobs = [], []
    for i, civic in enumerate(CIVICI):
        cid = f'C{i+1:03d}'
        kind = 'Rifornimento' if i < 40 else 'Manutenzione'
        clients.append([cid,DEMO_NAMES[i],civic['indirizzo'],str(civic['lat']),str(civic['lon']), 'Snack + Caffè' if i % 3 else 'Snack',f"Cliente simulato; civico e coordinate DS634 Comune di Milano; Municipio {civic['municipio']}."])
        jobs.append([f'I{i+1:03d}',day,cid,kind,'20' if i < 40 else '50',DEMO_SLOTS[i%len(DEMO_SLOTS)][0],DEMO_SLOTS[i%len(DEMO_SLOTS)][1],'Normale','Intervento dimostrativo'])
    replace('flotta',pd.DataFrame(vans,columns=['mezzo_id','targa','marca','modello','categoria','attivo']))
    replace('tecnici',pd.DataFrame(tech,columns=['tecnico_id','nome','cognome','ruolo','mezzo_id','indirizzo_partenza','lat','lon','inizio','fine','attivo']))
    replace('clienti',pd.DataFrame(clients,columns=['cliente_id','ragione_sociale','indirizzo','lat','lon','tipo_macchina','note']))
    replace('interventi',pd.DataFrame(jobs,columns=['intervento_id','data','cliente_id','tipo','durata_min','fascia_inizio','fascia_fine','priorita','note']))
    replace('presenze',pd.DataFrame([[day,t[0],'si'] for t in tech],columns=['data','tecnico_id','presente']))
    replace('magazzino',pd.DataFrame([],columns=['ritiro_id','data','tecnico_id','indirizzo','lat','lon','fascia_inizio','fascia_fine','durata_min']))
    return day


# SEZIONE: Aggiornamento non distruttivo delle sole postazioni dimostrative

def update_demo_addresses():
    clients = read('clienti')
    changed = 0
    for i, civic in enumerate(CIVICI):
        cid = f'C{i+1:03d}'
        mask = clients['cliente_id'].eq(cid) & clients['ragione_sociale'].isin([f'Punto ristoro {i+1:02d}', DEMO_NAMES[i]])
        if 'note' in clients:
            mask &= (clients['note'].str.contains('simulat|dimostrativ|Sede reale|Coordinate da geocodificare',case=False,na=False) | clients['indirizzo'].str.startswith('Postazione demo',na=False))
        if mask.any():
            clients.loc[mask,'indirizzo'] = civic['indirizzo']
            clients.loc[mask,'lat'] = str(civic['lat'])
            clients.loc[mask,'lon'] = str(civic['lon'])
            clients.loc[mask,'note'] = f"Cliente simulato; civico e coordinate DS634 Comune di Milano; Municipio {civic['municipio']}."
            changed += int(mask.sum())
    if changed:
        replace('clienti',clients)
    return changed
