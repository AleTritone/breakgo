# SEZIONE: Ottimizzazione dei percorsi e bilanciamento
import math
import pandas as pd
from ortools.constraint_solver import pywrapcp, routing_enums_pb2
from .geo import coordinate, matrix, minutes, road_geometry
from .store import read


def prepare(day):
    tech=read('tecnici')
    clients=read('clienti')
    jobs=read('interventi')
    attendance=read('presenze')
    stops=read('magazzino')
    jobs=jobs[jobs.data==day].copy()
    attendance=attendance[(attendance.data==day) & (attendance.presente.str.lower().isin(['si','sì','1','true','yes']))]
    tech=tech[tech.tecnico_id.isin(attendance.tecnico_id) & (tech.attivo.str.lower().isin(['si','sì','1','true','yes']))].copy()
    stops=stops[stops.data==day].copy()
    if jobs.empty:
        raise ValueError('Non sono presenti appuntamenti per la giornata selezionata.')
    if tech.empty:
        raise ValueError('Nessun tecnico presente: impostare le presenze della giornata.')
    # SEZIONE: Controlli di integrita delle anagrafiche
    for label, frame, key in (
        ('clienti', clients, 'cliente_id'),
        ('tecnici presenti', tech, 'tecnico_id'),
        ('appuntamenti', jobs, 'intervento_id'),
        ('ritiri in magazzino', stops, 'ritiro_id'),
    ):
        ids = frame[key].astype('string').fillna('').str.strip()
        duplicates = ids[ids.duplicated(keep=False) & ids.ne('')].unique().tolist()
        if duplicates:
            examples = ', '.join(map(str, duplicates[:8]))
            raise ValueError(
                f'Codici duplicati nell\'anagrafica {label}: {examples}. '
                'Correggi o elimina i duplicati nella sezione corrispondente '
                'prima di avviare l\'ottimizzazione.'
            )
    if jobs['cliente_id'].eq('').any():
        raise ValueError('Alcuni appuntamenti non hanno un cliente.')
    if not set(jobs.cliente_id).issubset(set(clients.cliente_id)):
        raise ValueError('Alcuni clienti degli appuntamenti non sono presenti in anagrafica.')
    if not set(stops.tecnico_id).issubset(set(tech.tecnico_id)):
        raise ValueError('Sono previsti passaggi in magazzino per tecnici assenti.')
    return tech, clients, jobs, stops


def role_problem(role, tech, clients, jobs, stops, speed, progress=None):
    crew=tech[tech.ruolo==role].reset_index(drop=True)
    tasks=jobs[jobs.tipo==role].reset_index(drop=True)
    if tasks.empty:
        return None
    if crew.empty:
        raise ValueError(f'Nessun tecnico presente per {role}, ma sono previsti {len(tasks)} interventi.')
    customers=clients.set_index('cliente_id')
    nodes=[]
    vehicles=[]
    for vi,t in crew.iterrows():
        start=len(nodes)
        nodes.append({'kind':'start','id':t.tecnico_id,'address':t.indirizzo_partenza,'lat':t.lat,'lon':t.lon,'service':0,'earliest':minutes(t.inizio),'latest':minutes(t.fine),'vehicle':vi,'cliente':''})
        if minutes(t.fine)<=minutes(t.inizio):
            raise ValueError(f'Orario di lavoro non valido per {t.tecnico_id}')
        vehicles.append({'id':t.tecnico_id,'nome':f'{t.nome} {t.cognome}'.strip(),'mezzo':t.mezzo_id,'start':start,'begin':minutes(t.inizio),'end':minutes(t.fine)})
    for _,job in tasks.iterrows():
        client=customers.loc[job.cliente_id]
        if isinstance(client, pd.DataFrame):
            raise ValueError(
                f'Il cliente {job.cliente_id} compare piu volte nell\'anagrafica. '
                'Assegna un codice cliente diverso a ogni postazione.'
            )
        nodes.append({'kind':'job','id':job.intervento_id,'address':client.indirizzo,'lat':client.lat,'lon':client.lon,'service':int(float(job.durata_min)),'earliest':minutes(job.fascia_inizio),'latest':minutes(job.fascia_fine),'vehicle':None,'cliente':f'{client.ragione_sociale} · {job.cliente_id}'})
    for _,stop in stops[stops.tecnico_id.isin(crew.tecnico_id)].iterrows():
        vi=next(i for i,v in enumerate(vehicles) if v['id']==stop.tecnico_id)
        nodes.append({'kind':'warehouse','id':stop.ritiro_id,'address':stop.indirizzo,'lat':stop.lat,'lon':stop.lon,'service':int(float(stop.durata_min)),'earliest':minutes(stop.fascia_inizio),'latest':minutes(stop.fascia_fine),'vehicle':vi,'cliente':'Magazzino'})
    for node in nodes:
        if node['earliest'] + node['service'] > node['latest']:
            raise ValueError(f'Fascia oraria troppo stretta per {node["id"]}')
    if progress:
        progress(f'Geocodifica {role.lower()} · {len(nodes)} tappe')
    unique={}
    for node in nodes:
        key=(node['address'],node['lat'],node['lon'])
        if key not in unique:
            unique[key]=coordinate(*key)
        node['coords']=unique[key]
    points=list(dict.fromkeys(n['coords'] for n in nodes))
    if progress:
        progress(f'Calcolo distanze {role.lower()} · {len(points)} località')
    km0,tm0,mode=matrix(points,speed)
    lookup={p:i for i,p in enumerate(points)}
    km=[[km0[lookup[a['coords']]][lookup[b['coords']]] for b in nodes] for a in nodes]
    tm=[[tm0[lookup[a['coords']]][lookup[b['coords']]] for b in nodes] for a in nodes]
    n=len(nodes); v=len(vehicles)
    manager=pywrapcp.RoutingIndexManager(n,v,[x['start'] for x in vehicles],[x['start'] for x in vehicles])
    routing=pywrapcp.RoutingModel(manager)
    def drive_cost(i,j):
        a,b=manager.IndexToNode(i),manager.IndexToNode(j)
        return int(round(km[a][b]*1000)) + tm[a][b]*40
    cost=routing.RegisterTransitCallback(drive_cost)
    routing.SetArcCostEvaluatorOfAllVehicles(cost)
    def drive_time(i,j):
        a,b=manager.IndexToNode(i),manager.IndexToNode(j)
        return int(tm[a][b]+nodes[a]['service'])
    transit=routing.RegisterTransitCallback(drive_time)
    routing.AddDimension(transit,1440,2880,False,'Time')
    clock=routing.GetDimensionOrDie('Time')
    for i,node in enumerate(nodes):
        if node['kind'] != 'start':
            clock.CumulVar(manager.NodeToIndex(i)).SetRange(node['earliest'],node['latest']-node['service'])
            if node['kind']=='warehouse':
                routing.VehicleVar(manager.NodeToIndex(i)).SetValue(int(node['vehicle']))
    for vi,veh in enumerate(vehicles):
        clock.CumulVar(routing.Start(vi)).SetRange(veh['begin'],veh['begin'])
        clock.CumulVar(routing.End(vi)).SetRange(veh['begin'],veh['end'])
        routing.AddVariableMinimizedByFinalizer(clock.CumulVar(routing.End(vi)))
    def visit_count(i,j):
        return 1 if nodes[manager.IndexToNode(j)]['kind']=='job' else 0
    count_index=routing.RegisterTransitCallback(visit_count)
    routing.AddDimension(count_index,0,len(tasks),True,'Jobs')
    count=routing.GetDimensionOrDie('Jobs')
    low=len(tasks)//v
    high=math.ceil(len(tasks)/v)
    for vi in range(v):
        end=count.CumulVar(routing.End(vi))
        end.SetRange(0,len(tasks))
        count.SetCumulVarSoftLowerBound(routing.End(vi),low,250000)
        count.SetCumulVarSoftUpperBound(routing.End(vi),high,250000)
    search=pywrapcp.DefaultRoutingSearchParameters()
    search.first_solution_strategy=routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    search.local_search_metaheuristic=routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    search.time_limit.seconds=10
    if progress:
        progress(f'Ottimizzazione {role.lower()} · {len(tasks)} interventi, {v} tecnici')
    solution=routing.SolveWithParameters(search)
    if not solution:
        raise ValueError(f'Nessuna soluzione fattibile per {role}. Verificare fasce orarie, durata, magazzini e orari dei tecnici.')
    routes=[]
    for vi,veh in enumerate(vehicles):
        idx=routing.Start(vi); seq=0; rows=[];total_km=0;drive=0;service=0
        while not routing.IsEnd(idx):
            ni=manager.IndexToNode(idx); node=nodes[ni]
            arrival=solution.Value(clock.CumulVar(idx))
            nxt=solution.Value(routing.NextVar(idx)); nj=manager.IndexToNode(nxt)
            rows.append({'ordine':seq,'tipo':node['kind'],'riferimento':node['id'],'cliente':node['cliente'],'indirizzo':node['address'],'arrivo':f'{arrival//60:02d}:{arrival%60:02d}','durata_min':node['service'],'lat':node['coords'][0],'lon':node['coords'][1]})
            total_km+=km[ni][nj];drive+=tm[ni][nj];service+=node['service']
            idx=nxt;seq+=1
        node=nodes[manager.IndexToNode(idx)]
        arrival=solution.Value(clock.CumulVar(idx))
        rows.append({'ordine':seq,'tipo':'return','riferimento':'Rientro','cliente':'','indirizzo':node['address'],'arrivo':f'{arrival//60:02d}:{arrival%60:02d}','durata_min':0,'lat':node['coords'][0],'lon':node['coords'][1]})
        if progress:
            progress(f'Tracciamento stradale · {veh["nome"]}')
        geometry=road_geometry(rows)
        routes.append({'geometria':geometry,'tecnico_id':veh['id'],'tecnico':veh['nome'],'ruolo':role,'mezzo_id':veh['mezzo'],'interventi':sum(r['tipo']=='job' for r in rows),'magazzini':sum(r['tipo']=='warehouse' for r in rows),'km':round(total_km,1),'guida_min':drive,'servizio_min':service,'impegno_min':arrival-veh['begin'],'tappe':rows})
    return {'ruolo':role,'modalita_distanze':mode,'routes':routes}


def optimize(day, speed=40, progress=None):
    tech,clients,jobs,stops=prepare(day)
    results=[]
    for role in ['Rifornimento','Manutenzione']:
        part=role_problem(role,tech,clients,jobs,stops,speed,progress)
        if part:
            results.append(part)
    routes=[r for part in results for r in part['routes']]
    return {'data':day,'modalita_distanze':list(dict.fromkeys(p['modalita_distanze'] for p in results)),'interventi_totali':sum(r['interventi'] for r in routes),'km_totali':round(sum(r['km'] for r in routes),1),'guida_totale_min':sum(r['guida_min'] for r in routes),'routes':routes}
