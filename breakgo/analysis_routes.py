# SEZIONE: Ricostruzione stradale delle assegnazioni
import hashlib
import json
import requests
from .store import read, load_solution, save_solution
from .board import get_assignments, extras
from .geo import coordinate, OSRM, HEADERS


def snapshot(day):
    assignments=get_assignments(day)
    jobs=read('interventi');jobs=jobs[jobs.data.astype(str)==str(day)]
    technicians=read('tecnici')
    clients=read('clienti').drop_duplicates('cliente_id').set_index('cliente_id')
    warehouses=read('magazzino');warehouses=warehouses[warehouses.data.astype(str)==str(day)]
    presences=read('presenze');presences=presences[(presences.data.astype(str)==str(day)) & (presences.presente.astype(str).str.lower().isin(['si','sì','true','1','yes']))]
    present=set(presences.tecnico_id.astype(str))
    roster={str(t.tecnico_id):t for _,t in technicians.iterrows() if str(t.tecnico_id) in present}
    grouped={tid:[] for tid in roster}
    for _,job in jobs.iterrows():
        key='job:'+str(job.intervento_id);tid=assignments.get(key,'')
        if tid not in grouped or str(job.cliente_id) not in clients.index:continue
        c=clients.loc[str(job.cliente_id)]
        grouped[tid].append({'key':key,'tipo':'Intervento','riferimento':str(c.ragione_sociale),'indirizzo':str(c.indirizzo),'fascia_inizio':str(job.fascia_inizio),'fascia_fine':str(job.fascia_fine),'durata_min':float(job.durata_min or 0)})
    for _,w in warehouses.iterrows():
        tid=str(w.tecnico_id)
        if tid in grouped:
            grouped[tid].append({'key':'warehouse:'+str(w.ritiro_id),'tipo':'Magazzino','riferimento':'Ritiro in magazzino','indirizzo':str(w.indirizzo),'fascia_inizio':str(w.fascia_inizio),'fascia_fine':str(w.fascia_fine),'durata_min':float(w.durata_min or 0)})
    for e in extras(day):
        tid=str(e['tecnico_id'])
        if tid in grouped:
            grouped[tid].append({'key':str(e['id']),'tipo':str(e['categoria']),'riferimento':str(e['descrizione']),'indirizzo':str(e['indirizzo']),'fascia_inizio':str(e['fascia_inizio']),'fascia_fine':str(e['fascia_fine']),'durata_min':float(e['durata_min'] or 0)})
    for items in grouped.values():items.sort(key=lambda x:(x['fascia_inizio'],x['fascia_fine'],x['key']))
    payload={'day':day,'roster':{tid:{'nome':str(t.nome)+' '+str(t.cognome),'ruolo':str(t.ruolo),'mezzo_id':str(t.mezzo_id),'partenza':str(t.indirizzo_partenza)} for tid,t in roster.items()},'grouped':grouped}
    signature=hashlib.sha256(json.dumps(payload,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
    return payload,signature


def calculate(day, progress=None):
    payload,signature=snapshot(day)
    routes=[]; errors=[]
    for tid,items in payload['grouped'].items():
        if not items:continue
        t=payload['roster'][tid]
        if progress:progress(f'Calcolo stradale: {t["nome"]}...')
        addresses=[t['partenza']]+[x['indirizzo'] or t['partenza'] for x in items]+[t['partenza']]
        try:
            coords=[coordinate(address) for address in addresses]
            coords_string=';'.join(f'{lon:.6f},{lat:.6f}' for lat,lon in coords)
            response=requests.get(OSRM+'/route/v1/driving/'+coords_string,params={'overview':'full','geometries':'geojson','steps':'false'},headers=HEADERS,timeout=120)
            response.raise_for_status();data=response.json()
            if data.get('code')!='Ok' or not data.get('routes'):raise ValueError(str(data.get('message',data.get('code'))))
            r=data['routes'][0];legs=r.get('legs',[])
            if len(legs)!=len(addresses)-1:raise ValueError('Numero tratte stradali non coerente')
            stops=[];clock=None
            for i,item in enumerate(items):
                lat,lon=coords[i+1]
                stops.append({'ordine':i+1,'tipo':item['tipo'],'riferimento':item['riferimento'],'indirizzo':item['indirizzo'],'fascia_inizio':item['fascia_inizio'],'fascia_fine':item['fascia_fine'],'durata_min':item['durata_min'],'km_dalla_tappa_precedente':round(legs[i]['distance']/1000,2),'guida_dalla_tappa_precedente_min':round(legs[i]['duration']/60,1),'lat':lat,'lon':lon})
            routes.append({'tecnico_id':tid,'tecnico':t['nome'],'ruolo':t['ruolo'],'mezzo_id':t['mezzo_id'],'interventi':sum(x['tipo']=='Intervento' for x in items),'magazzini':sum(x['tipo']=='Magazzino' for x in items),'km':round(r['distance']/1000,2),'guida_min':round(r['duration']/60,1),'servizio_min':sum(x['durata_min'] for x in items if x['tipo']=='Intervento'),'impegno_min':sum(x['durata_min'] for x in items),'rientro_km':round(legs[-1]['distance']/1000,2),'rientro_min':round(legs[-1]['duration']/60,1),'tappe':stops,'geometria':[[lat,lon] for lon,lat in r['geometry']['coordinates']]})
        except (requests.RequestException,ValueError,KeyError,TypeError,IndexError) as exc:
            errors.append(f'{t["nome"]}: {exc}')
    result={'data':day,'routes':routes,'signature':signature,'errors':errors,'source':'OSRM - rete stradale OpenStreetMap, senza traffico in tempo reale'}
    save_solution(day,result)
    return result


def cached(day):
    result=load_solution(day)
    if not result or 'signature' not in result:return None
    _,signature=snapshot(day)
    return result if result.get('signature')==signature else None
