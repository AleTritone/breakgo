# SEZIONE: Interfaccia e stile
import io
import html
from pathlib import Path
import json
from datetime import date
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
import folium
from .schema import TABLES, LABELS
from .store import read, replace, validate, save_solution, load_solution
from .excel import workbook, read_upload
from .sample import seed, update_demo_addresses, update_demo_records
from .optimizer import optimize
from .guided import registry, warehouse_form
from .board import get_assignments, save_assignments, extras, add_extra, remove_extra, get_manual, set_manual, clear_manual, plan_progressively
import streamlit.components.v1 as streamlit_components

_BOARD_COMPONENT = streamlit_components.declare_component("breakgo_trello", path=str(Path(__file__).resolve().parent.parent / "assets" / "trello_component"))


def theme():
    # SEZIONE: Caricamento del tema CSS esterno
    css_path = Path(__file__).resolve().parent.parent / 'assets' / 'breakgo.css'
    if css_path.is_file():
        st.markdown('<style>' + css_path.read_text(encoding='utf-8') + '</style>', unsafe_allow_html=True)


def banner():
    import base64
    image_path=Path(__file__).resolve().parent.parent/'assets'/'banner_breakgo.png'
    if image_path.exists():
        encoded=base64.b64encode(image_path.read_bytes()).decode('ascii')
        st.markdown(f'<div class="brand-banner"><img src="data:image/png;base64,{encoded}" alt="Break&Go: furgone snack e caffe"></div>',unsafe_allow_html=True)


def hero(title,subtitle,tag='BREAK&GO · OPERATIONS'):
    st.markdown(f'<div class="hero"><div class="eyebrow">{tag}</div><h1>{title}</h1><p>{subtitle}</p></div>',unsafe_allow_html=True)


def metric(label,value,hint='',variant=''):
    st.markdown(f'<div class="metric-card {variant}"><div class="label">{html.escape(str(label))}</div><div class="value">{html.escape(str(value))}</div><div class="hint">{html.escape(str(hint))}</div></div>',unsafe_allow_html=True)


def quick_card(icon,title,description,variant=''):
    st.markdown(f'<div class="quick-card {variant}"><div class="ico">{icon}</div><strong>{html.escape(title)}</strong><small>{html.escape(description)}</small></div>',unsafe_allow_html=True)


def sheet_editor(table):
    title=LABELS[table]
    df=read(table)
    st.subheader(title)
    st.caption('Modifica le celle e premi Salva. I dati sono conservati in SQLite anche dopo il riavvio.')
    with st.expander('Importa da Excel',expanded=False):
        left,right=st.columns([2,1])
        with left:
            uploaded=st.file_uploader(f'File Excel · {title}',type='xlsx',key=f'upload_{table}')
        with right:
            st.download_button('Scarica modello Excel',workbook({table:pd.DataFrame(columns=TABLES[table])}),file_name=f'modello_{table}.xlsx',key=f'model_{table}')
        if uploaded is not None and st.button('Importa e sostituisci dati',key=f'import_{table}',type='primary'):
            try:
                incoming=validate(table,read_upload(uploaded,table))
                replace(table,incoming)
                st.success(f'Importate {len(incoming)} righe')
                st.rerun()
            except Exception as exc:
                st.error(str(exc))
    editor=st.data_editor(df,num_rows='dynamic',hide_index=True,width='stretch',key=f'editor_{table}',height=min(580,max(220,80+len(df)*35)))
    a,b=st.columns([1,1])
    with a:
        if st.button('Salva modifiche',type='primary',key=f'save_{table}'):
            try:
                clean=validate(table,editor)
                replace(table,clean)
                st.success(f'Salvate {len(clean)} righe')
                st.rerun()
            except Exception as exc:
                st.error(str(exc))
    with b:
        st.download_button('Esporta anagrafica Excel',workbook({table:df}),file_name=f'breakgo_{table}.xlsx',key=f'export_{table}')
    if table=='tecnici':
        st.info('Ruolo: Rifornimento oppure Manutenzione. Attivo: si/no. Il mezzo_id deve esistere nella Flotta. Basta l’indirizzo: la posizione viene individuata automaticamente.')
    elif table=='interventi':
        st.info('Ogni appuntamento indica cliente, data, tipologia, durata e fascia oraria. L’assegnazione automatica avviene salvando le presenze.')
    elif table=='magazzino':
        st.info('Inserisci una riga per ogni passaggio: puoi impostare 0, 1 o più ritiri per tecnico, ognuno con fascia e durata indipendenti.')


def navigate_to(target):
    st.session_state['nav_page'] = target


def home():
    banner()
    st.title('Il tuo centro operativo')
    st.markdown('<div class="section-note"><b>①</b> Registra flotta e tecnici &nbsp; ➜ &nbsp; <b>②</b> Importa i punti ristoro &nbsp; ➜ &nbsp; <b>③</b> Inserisci gli appuntamenti &nbsp; ➜ &nbsp; <b>④</b> Pianifica la giornata</div>',unsafe_allow_html=True)
    tech=read('tecnici');fleet=read('flotta');clients=read('clienti');jobs=read('interventi')
    today=date.today().isoformat()
    today_jobs=jobs[jobs.data==today] if len(jobs) else jobs
    refill=sum(tech.ruolo=='Rifornimento') if len(tech) else 0
    maintenance=sum(tech.ruolo=='Manutenzione') if len(tech) else 0
    c1,c2,c3,c4=st.columns(4)
    with c1:metric('👥 Tecnici totali',len(tech),f'{refill} rifornimento · {maintenance} manutenzione')
    with c2:metric('🚐 Furgoni in flotta',len(fleet),'Ducato e Scudo','yellow')
    with c3:metric('📍 Punti ristoro',len(clients),'Attivi sul territorio','mint')
    with c4:metric('📅 Appuntamenti oggi',len(today_jobs),f'{sum(today_jobs.tipo=="Rifornimento")} rifornimenti · {sum(today_jobs.tipo=="Manutenzione")} manutenzioni' if len(today_jobs) else 'Nessun intervento oggi','rose')
    st.write('')
    st.subheader('Accesso rapido')
    cards=[('👥','Squadra e ruoli','Gestisci tecnici e competenze','Tecnici'),('🚐','Flotta','Registra e gestisci i furgoni','Flotta'),('📍','Punti ristoro','Importa clienti e postazioni','Clienti e postazioni'),('📅','Appuntamenti','Crea o importa gli interventi','Appuntamenti'),('🗺️','Pianificazione','Presenze, ritiri e percorsi','Programmazione giornata')]
    columns=st.columns(5)
    for i,(ico,title,desc,target) in enumerate(cards):
        with columns[i]:
            quick_card(ico,title,desc,'yellow' if i%2 else '')
            st.button('Apri sezione →', key=f'quick_{i}', use_container_width=True, on_click=navigate_to, args=(target,))
    st.write('')
    left,right=st.columns([1.25,1])
    with left:
        st.subheader('Ultima pianificazione')
        available=sorted([x for x in jobs.data.unique() if x],reverse=True) if len(jobs) else []
        latest=load_solution(available[0]) if available else None
        if latest:
            st.success(f'Pianificazione disponibile · {latest["data"]} · {latest["interventi_totali"]} interventi · {latest["km_totali"]:.1f} km')
            st.button('Visualizza dettagli', key='home_plan', on_click=navigate_to, args=('Analisi giornata lavorativa',))
        else:
            st.info('Nessuna pianificazione salvata. Salva le presenze nella Programmazione giornata.')
        st.subheader('Squadra e ruoli')
        if len(tech):st.dataframe(tech[['nome','cognome','ruolo','mezzo_id','attivo']],hide_index=True,width='stretch')
        else:st.info('Non ci sono ancora tecnici registrati.')
    with right:
        st.subheader('Documenti utili')
        st.download_button('⬇ Scarica modello Excel',workbook({k:pd.DataFrame(columns=v) for k,v in TABLES.items()}),file_name='breakgo_modello.xlsx',use_container_width=True)
        st.download_button('⬇ Esporta archivio completo',workbook({k:read(k) for k in TABLES}),file_name='breakgo_archivio.xlsx',use_container_width=True)
        with st.expander('Carica azienda dimostrativa'):
            st.write('5 tecnici, 5 furgoni, 40 rifornimenti e 4 manutenzioni. La demo sostituisce i dati esistenti.')
            if st.button('Conferma caricamento demo',type='primary'):
                try:
                    day=seed()
                    st.success(f'Dati demo creati per {day}')
                    st.rerun()
                except Exception as exc:st.error(str(exc))
            st.caption('Indirizzi civici reali di Milano. Clienti e distributori simulati. Le coordinate sono geocodificate al primo calcolo.')
            if st.button('Aggiorna nomi e fasce orarie della demo',key='update_demo_records'):
                n,m=update_demo_records()
                if n or m: st.success(f'Aggiornati {n} nomi e {m} fasce orarie dimostrative.'); st.rerun()
                else: st.info('Nessun record dimostrativo originale da aggiornare.')
            if st.button('Distribuisci i 44 punti su tutta Milano',key='update_demo_addresses'):
                n=update_demo_addresses()
                if n: st.success(f'Aggiornati {n} indirizzi dimostrativi.'); st.rerun()
                else: st.info('Nessun vecchio indirizzo demo da aggiornare.')


def _save_presence_and_plan(day, options, selected, existing):
    other=existing[existing.data!=day]
    today=pd.DataFrame([{'data':day,'tecnico_id':tid,'presente':'si' if tid in selected else 'no'} for tid in options])
    replace('presenze',pd.concat([other,today],ignore_index=True))
    try:
        with st.spinner('Assegnazione progressiva per priorità e percorrenza stradale...'):
            assigned, issues=plan_progressively(day,selected)
        st.success(f'Presenze salvate. {sum(bool(t) for k,t in assigned.items() if k.startswith("job:"))} interventi assegnati; {sum(not t for k,t in assigned.items() if k.startswith("job:"))} da rimodulare.')
        if issues:
            with st.expander(f'{len(issues)} segnalazioni di pianificazione'):
                for issue in issues:st.write(issue)
    except Exception as exc:
        st.error(f'Presenze salvate; pianificazione non completata: {exc}')
        st.info('Le assegnazioni manuali precedenti sono conservate.')



def _board(day, selected, tech):
    st.subheader('Bacheca assegnazioni')
    st.caption('Trascina le schede compatte tra i tecnici e i non assegnati. Ogni colonna resta ordinata per fascia oraria; usa + sotto il tecnico per aggiungere attività.')
    jobs=read('interventi'); jobs=jobs[jobs.data==day]
    clients=read('clienti')
    client_names={r.cliente_id:r.ragione_sociale for _,r in clients.iterrows()}
    warehouses=read('magazzino'); warehouses=warehouses[warehouses.data==day]
    assignment=get_assignments(day)
    manual=get_manual(day)
    entries={}
    for _,j in jobs.iterrows():
        key='job:'+str(j.intervento_id)
        entries[key]={'start':str(j.fascia_inizio),'end':str(j.fascia_fine),'role':str(j.tipo),'title':str(client_names.get(j.cliente_id,j.cliente_id)),'detail':str(j.intervento_id),'type':'Intervento'}
    for _,w in warehouses.iterrows():
        key='warehouse:'+str(w.ritiro_id)
        entries[key]={'start':str(w.fascia_inizio),'end':str(w.fascia_fine),'role':'','title':'Ritiro magazzino','detail':str(w.indirizzo),'type':'Magazzino'}
        assignment.setdefault(key,str(w.tecnico_id))
    for x in extras(day):
        entries[x['id']]={'start':x['fascia_inizio'],'end':x['fascia_fine'],'role':'','title':x['descrizione'],'detail':x['motivazione'] or x['indirizzo'],'type':x['categoria']}
        assignment.setdefault(x['id'],x['tecnico_id'])
    selected=[str(t) for t in selected]
    names={str(r.tecnico_id):f'{r.nome} {r.cognome}' for _,r in tech.iterrows()}
    roles={str(r.tecnico_id):str(r.ruolo) for _,r in tech.iterrows()}
    columns=['']+selected
    def sortkey(key):
        e=entries[key]
        return (e['start'],e['end'],key)
    cards=[]
    for tid in columns:
        keys=sorted([k for k in entries if assignment.get(k,'')==tid or (tid=='' and assignment.get(k,'') not in selected)],key=sortkey)
        cards.append({'id':tid,'name':'Non assegnati' if tid=='' else names.get(tid,tid),
                      'items':[{'id':key,'start':entries[key]['start'],'end':entries[key]['end'],
                                'title':entries[key]['title'],'detail':entries[key]['detail'],
                                'locked':key in manual,'type':entries[key]['type']} for key in keys]})
    if not entries:
        st.info('Non ci sono interventi per questa data. Puoi crearne uno dalla bacheca.')
    event=_BOARD_COMPONENT(columns=cards, clients=[{'id':str(r.cliente_id),'name':str(r.ragione_sociale)} for _,r in clients.iterrows()], key='trello_'+day, default=None)
    if isinstance(event,dict) and event.get('nonce') != st.session_state.get('trello_last_'+day):
        st.session_state['trello_last_'+day]=event.get('nonce')
        if event.get('action')=='move':
            key=str(event.get('item',''));tid=str(event.get('target',''))
            if key in entries and tid in columns:
                if key.startswith('job:') and tid and entries[key]['role']!=roles.get(tid):
                    st.error('Questo tecnico non ha la competenza richiesta per l’intervento.')
                elif assignment.get(key,'') != tid:
                    set_manual(day,key,tid)
                    assignment[key]=tid
                    save_assignments(day,{k:v for k,v in assignment.items() if k in entries})
                    st.rerun()
        elif event.get('action')=='create':
            tid=str(event.get('target',''))
            category=str(event.get('category','')).strip()
            description=str(event.get('description','')).strip()
            address=str(event.get('address','')).strip()
            begin=str(event.get('start',''))
            finish=str(event.get('end',''))
            reason=str(event.get('reason','')).strip()
            try:
                duration=int(event.get('duration',30))
                if tid=='':
                    client=str(event.get('client',''))
                    kind=str(event.get('kind','Rifornimento'))
                    if client not in set(clients.cliente_id.astype(str)):
                        st.error('Seleziona un cliente valido.')
                    else:
                        from uuid import uuid4
                        new_id='INT-'+uuid4().hex[:10].upper()
                        row={'intervento_id':new_id,'data':day,'cliente_id':client,'tipo':kind,'durata_min':str(duration),'fascia_inizio':begin,'fascia_fine':finish,'priorita':str(event.get('priority','Normale')),'note':reason}
                        if not description or begin>=finish or duration<1:
                            st.error('Controlla descrizione, durata e fascia oraria.')
                        else:
                            replace('interventi',pd.concat([read('interventi'),pd.DataFrame([row])],ignore_index=True))
                            st.rerun()
                elif not description or not (0<duration<=600) or begin>=finish:
                    st.error('Controlla descrizione, durata e fascia oraria.')
                elif category=='Ritiro magazzino' and not address:
                    st.error('Inserisci l’indirizzo del magazzino.')
                else:
                    key=add_extra(day,tid,category,description,address,begin,finish,duration,reason)
                    current=get_assignments(day)
                    current[key]=tid
                    save_assignments(day,current)
                    st.rerun()
            except (ValueError,TypeError) as exc:
                st.error(f'Attività non valida: {exc}')
    if manual:
        with st.expander('Assegnazioni manuali bloccate'):
            for key,tid in manual.items():
                if key in entries:
                    a,b=st.columns([5,1])
                    with a:st.caption(f'{entries[key]["title"]} → {names.get(tid,"Non assegnato")}')
                    with b:
                        if st.button('Sblocca',key='unlock_'+day+key):
                            clear_manual(day,key);st.rerun()
    counts={tid:sum(assignment.get(k,'')==tid and k.startswith('job:') for k in entries) for tid in selected}
    if counts:
        st.caption('Interventi assegnati: '+ ' · '.join(f'{names.get(t,t)}: {counts[t]}' for t in selected))
    xlist=extras(day)
    if xlist:
        with st.expander('Rimuovi pause, ritiri o impegni aggiunti'):
            choices={x['id']:f'{x["descrizione"]} · {x["fascia_inizio"]} · {names.get(x["tecnico_id"],x["tecnico_id"])}' for x in xlist}
            chosen=st.selectbox('Attività da rimuovere',list(choices),format_func=lambda x:choices[x])
            if st.button('Rimuovi attività',key='delete_extra_'+day):
                remove_extra(chosen)
                st.rerun()
    st.info('Gli spostamenti manuali modificano le assegnazioni della bacheca. Le distanze e gli orari stradali del piano automatico precedente non vengono ricalcolati finché non si genera una nuova pianificazione.')


def planning():
    hero('Programmazione giornaliera','Salva le presenze per generare l’assegnazione ottimizzata. Modifica poi il piano trascinando gli interventi nella bacheca.','BREAK&GO · PIANIFICAZIONE')
    day=st.date_input('Giornata di lavoro',value=date.today(),key='planning_date').isoformat()
    tech=read('tecnici')
    existing=read('presenze')
    current=existing[existing.data==day]
    present=set(current[current.presente.str.lower().isin(['si','sì','1','true','yes'])].tecnico_id)
    if current.empty:
        present=set(tech[tech.attivo.str.lower().isin(['si','sì','1','true','yes'])].tecnico_id)
    options=tech['tecnico_id'].tolist()
    names={r.tecnico_id:f'{r.nome} {r.cognome} · {r.ruolo}' for _,r in tech.iterrows()}
    selected=st.multiselect('Tecnici presenti',options,default=[x for x in options if x in present],format_func=lambda x:names.get(x,x),key='present_'+day)
    if st.button('Salva presenze e genera assegnazione ottimizzata',type='primary'):
        _save_presence_and_plan(day,options,selected,existing)
    st.caption('Le assegnazioni manuali restano bloccate anche dopo il ricalcolo. Gli interventi non fattibili rimangono non assegnati.')
    _board(day,selected,tech)


def route_map(routes):
    if not routes:
        return
    first=routes[0]['tappe'][0]
    fmap=folium.Map(location=[first['lat'],first['lon']],zoom_start=11,tiles='OpenStreetMap')
    colors=['#0DAE94','#E88D37','#367BC8','#8C66C7','#D4536E','#577C39','#A86B4E']
    for i,r in enumerate(routes):
        color=colors[i%len(colors)]
        coords=r.get('geometria')
        if not coords:
            st.warning(f'Percorso stradale non disponibile per {r["tecnico"]}: riesegui l’ottimizzazione.')
            continue
        folium.PolyLine(coords,color=color,weight=5,opacity=.85,tooltip=f'{r["tecnico"]} · {r["km"]} km').add_to(fmap)
        for stop in r['tappe']:
            folium.CircleMarker([stop['lat'],stop['lon']],radius=6 if stop['tipo']=='job' else 9,color=color,fill=True,fill_opacity=.85,tooltip=f'{r["tecnico"]}: {stop["riferimento"]} · {stop.get("arrivo",stop.get("fascia_inizio",""))}').add_to(fmap)
    components.html(fmap._repr_html_(),height=540,scrolling=False)
    st.caption('Tracciati lungo le strade OpenStreetMap, calcolati da OSRM. Tempi stimati senza traffico in tempo reale.')


def results_view(result):
    st.success('Piano calcolato e salvato. I risultati rimangono disponibili anche dopo il riavvio.')
    st.caption('Distanze: '+', '.join(result['modalita_distanze']))
    a,b,c=st.columns(3)
    with a:metric('Interventi assegnati',result['interventi_totali'])
    with b:metric('Km complessivi',f'{result["km_totali"]:,.1f}')
    with c:metric('Minuti di guida',result['guida_totale_min'])
    summary=pd.DataFrame([{k:r[k] for k in ('tecnico','ruolo','mezzo_id','interventi','magazzini','km','guida_min','servizio_min','impegno_min')} for r in result['routes']])
    st.subheader('Carico di lavoro per tecnico')
    st.dataframe(summary,width='stretch',hide_index=True)
    st.bar_chart(summary.set_index('tecnico')[['interventi']])
    st.subheader('Mappa dei giri')
    route_map(result['routes'])
    st.subheader('Schede percorso')
    tables={'Riepilogo':summary}
    for r in result['routes']:
        name=r['tecnico_id']
        with st.expander(f'{r["tecnico"]} · {r["ruolo"]} · {r["interventi"]} interventi · {r["km"]} km'):
            st.dataframe(pd.DataFrame(r['tappe']).drop(columns=['lat','lon']),width='stretch',hide_index=True)
        tables[name]=pd.DataFrame(r['tappe'])
    st.download_button('Scarica piano operativo Excel',workbook(tables),file_name=f'breakgo_giri_{result["data"]}.xlsx',type='primary')


# SEZIONE: Analisi operativa per periodo e tecnico
def work_analysis():
    from .analysis_routes import cached, calculate
    hero('Analisi giornata lavorativa','Carico di lavoro, percorrenze stradali e dettaglio dei giri per periodo e tecnico.','BREAK&GO · ANALISI')
    jobs=read('interventi')
    if jobs.empty:
        st.info('Non sono presenti appuntamenti da analizzare.');return
    available=sorted(set(str(x) for x in jobs.data if x))
    a,b,c=st.columns([1,1,2])
    with a:start=st.date_input('Dal',value=pd.to_datetime(available[-1]).date(),key='analysis_start')
    with b:end=st.date_input('Al',value=pd.to_datetime(available[-1]).date(),key='analysis_end')
    tech=read('tecnici');names={str(t.tecnico_id):f'{t.nome} {t.cognome}' for _,t in tech.iterrows()}
    with c:selected=st.selectbox('Tecnico',['']+list(names),format_func=lambda x:names.get(x,'Tutti i tecnici'),key='analysis_tech')
    if start>end:st.warning('La data iniziale deve precedere quella finale.');return
    days=[d for d in available if start.isoformat()<=d<=end.isoformat()]
    if not days:st.info('Nessun appuntamento nel periodo selezionato.');return
    rows=[];routes=[];missing=[];errors=[]
    for day in days:
        assignments=get_assignments(day)
        for _,j in jobs[jobs.data==day].iterrows():
            tid=assignments.get('job:'+str(j.intervento_id),'')
            if selected and tid!=selected:continue
            rows.append({'Data':day,'Tecnico':names.get(tid,'Non assegnato'),'Tecnico ID':tid,'Assegnato':bool(tid),'Tipo':str(j.tipo),'Priorità':str(j.priorita),'Durata prevista (min)':float(pd.to_numeric(j.durata_min,errors='coerce')) if pd.notna(pd.to_numeric(j.durata_min,errors='coerce')) else 0})
        saved=cached(day)
        if saved:
            errors.extend(f'{day}: {e}' for e in saved.get('errors',[]))
            routes.extend((day,r) for r in saved.get('routes',[]) if not selected or str(r.get('tecnico_id'))==selected)
        else:missing.append(day)
    df=pd.DataFrame(rows)
    if df.empty:st.info('Nessun intervento per il filtro selezionato.');return
    total=len(df);assigned=int(df.Assegnato.sum());distance=sum(float(r['km']) for _,r in routes);driving=sum(float(r['guida_min']) for _,r in routes)
    k1,k2,k3,k4=st.columns(4)
    with k1:st.metric('Interventi pianificati',total)
    with k2:st.metric('Assegnati',f'{assigned}/{total}',f'{assigned/total:.0%}')
    with k3:st.metric('Da rimodulare',total-assigned)
    with k4:st.metric('Km stradali stimati',f'{distance:,.1f}' if routes else 'Non calcolati')
    if missing:
        st.info('Percorsi non ancora calcolati, oppure modificati dopo l’ultimo calcolo: '+', '.join(missing)+'. Generali per ottenere mappa, km e tempi stradali.')
        if st.button('Calcola / aggiorna i percorsi stradali',type='primary',key='analysis_calc'):
            status=st.empty()
            with st.spinner('Geocodifica e calcolo stradale in corso...'):
                for day in missing:calculate(day,lambda message:status.info(message))
            status.empty();st.rerun()
    if errors:st.warning('Alcuni giri non sono stati calcolati: '+' | '.join(errors))
    st.caption('Distanze e tempi: stime OSRM su strade reali, senza traffico live. Non sono consuntivi GPS. La durata degli interventi è quella prevista.')
    st.subheader('Carico di lavoro')
    summary=df[df.Assegnato].groupby('Tecnico').agg(Interventi=('Assegnato','size'),Servizio_min=('Durata prevista (min)','sum')).reset_index()
    if not summary.empty:
        left,right=st.columns(2)
        with left:
            st.caption('Interventi per tecnico')
            st.bar_chart(summary.set_index('Tecnico')['Interventi'],horizontal=True)
        with right:
            st.caption('Minuti di servizio previsti per tecnico')
            st.bar_chart(summary.set_index('Tecnico')['Servizio_min'],horizontal=True)
    if len(days)>1:
        st.subheader('Andamento nel periodo')
        trend=df.groupby('Data').agg(Interventi=('Assegnato','size'),Assegnati=('Assegnato','sum'))
        st.line_chart(trend)
    if routes:
        st.subheader('Tempi e percorrenze')
        road=pd.DataFrame([{'Data':day,'Tecnico':r['tecnico'],'Km':r['km'],'Guida (min)':r['guida_min'],'Servizio (min)':r['servizio_min'],'Impegno (min)':r['impegno_min']} for day,r in routes])
        x,y,z=st.columns(3)
        with x:st.metric('Guida stimata',f'{driving:,.0f} min')
        with y:st.metric('Servizio previsto',f'{road["Servizio (min)"].sum():,.0f} min')
        with z:st.metric('Impegno complessivo stimato',f'{(road["Guida (min)"].sum()+road["Impegno (min)"].sum()):,.0f} min')
        st.dataframe(road,hide_index=True,width='stretch')
        st.subheader('Mappa dei giri stradali')
        route_map([r for _,r in routes if r.get('tappe') and r.get('geometria')])
    else:
        st.info('La mappa sarà disponibile dopo il calcolo stradale dei giri.')
    st.subheader('Riepilogo degli spostamenti per tecnico')
    if routes:
        for day,r in routes:
            with st.expander(f'{day} · {r["tecnico"]} · {r["km"]:,.1f} km · {r["guida_min"]:,.0f} min di guida',expanded=len(routes)<=5):
                st.write(f'**Interventi:** {r["interventi"]} · **Magazzini:** {r["magazzini"]} · **Servizio previsto:** {r["servizio_min"]:,.0f} min · **Rientro:** {r.get("rientro_km",0):,.1f} km / {r.get("rientro_min",0):,.0f} min')
                stops=pd.DataFrame(r.get('tappe',[]))
                if not stops.empty:st.dataframe(stops.drop(columns=['lat','lon'],errors='ignore'),hide_index=True,width='stretch')
    else:st.caption('Nessun riepilogo stradale disponibile. Avvia il calcolo qui sopra.')
    st.download_button('Esporta interventi del periodo',workbook({'Interventi':df}),file_name='breakgo_analisi.xlsx')


def bio_page():
    # Profilo dell'autore e presentazione della rubrica divulgativa.
    import base64
    portrait=Path(__file__).resolve().parent.parent / 'assets' / 'alessandro_marrazzo.jpg'
    photo=''
    if portrait.is_file():
        photo=base64.b64encode(portrait.read_bytes()).decode('ascii')
    st.markdown('<div class="bio-eyebrow">BREAK&GO · CHI C’È DIETRO IL PROGETTO</div>',unsafe_allow_html=True)
    if photo:
        st.markdown(f"""<div class="bio-hero"><img class="bio-portrait" src="data:image/jpeg;base64,{photo}" alt="Ritratto illustrato di Alessandro Marrazzo"><div><div class="bio-kicker">AUTORE E SVILUPPATORE</div><h1>Alessandro Marrazzo</h1><p class="bio-role">Sviluppatore BI · Settore telecomunicazioni</p><a class="bio-link" href="https://www.linkedin.com/in/alessandro-marrazzo-518806385/" target="_blank" rel="noopener noreferrer">Profilo LinkedIn ↗</a></div></div>""",unsafe_allow_html=True)
    else:
        st.title('Alessandro Marrazzo')
        st.link_button('Profilo LinkedIn','https://www.linkedin.com/in/alessandro-marrazzo-518806385/')
    st.markdown("""<div class="bio-content"><div class="bio-section-title">La mia storia, tra dati e curiosità</div><p>Sono <strong>Alessandro Marrazzo</strong> e lavoro come <strong>sviluppatore BI per un'azienda di telecomunicazioni</strong>. La matematica e l'analisi dei dati sono tra le mie passioni: mi affascina l'idea di trasformare numeri e informazioni in strumenti utili per interpretare la realtà e prendere decisioni più consapevoli.</p><p>Negli ultimi tempi sto approfondendo il <strong>machine learning</strong> e la <strong>data science</strong>, esplorando metodi e tecnologie che ampliano le possibilità di analisi. Mi interessano in particolare le relazioni tra parole e concetti, le <strong>rappresentazioni vettoriali del linguaggio</strong> e i modelli probabilistici che permettono di studiare associazioni, somiglianze e affinità semantiche.</p><p>Fuori dal lavoro studio e scrivo racconti. Mi dedico anche alla <strong>divulgazione sull'uso moderno di Excel</strong>, cercando di mostrare come uno strumento così diffuso possa essere utilizzato per affrontare problemi complessi, organizzare informazioni e costruire analisi efficaci.</p><p>Un'altra mia passione è approfondire la <strong>biomeccanica sportiva</strong> e la <strong>sport analytics</strong>, osservando le prestazioni dei grandi campioni, del presente e del passato, attraverso la lente dei dati. Questi approfondimenti sono soprattutto un laboratorio personale di <strong>ricerca sulla data visualization e sul data storytelling</strong>: mi permettono di sperimentare soluzioni sempre più sofisticate per rappresentare fenomeni, mettere in relazione variabili e costruire narrazioni capaci di far emergere aspetti meno evidenti.</p><p>In questo percorso esploro strumenti come <strong>Power BI</strong> e <strong>Vega/Vega-Lite</strong>, insieme a librerie Python quali <strong>Matplotlib, Plotly, Seaborn e NetworkX</strong>, passando dai grafici statistici alle visualizzazioni interattive e alle reti di relazioni. Gli articoli che pubblico su <strong>LinkedIn</strong> sono parte di questo processo: occasioni per approfondire un argomento, mettere alla prova nuove idee e condividere i risultati delle mie sperimentazioni.</p><div class="bio-tags"><span>Matematica</span><span>Data analysis</span><span>Business Intelligence</span><span>Machine learning</span><span>Excel</span><span>Sport analytics</span><span>Scrittura</span></div></div><div class="bio-project"><div class="bio-section-title">Perché Break&Go</div><p><strong>Break&Go</strong> nasce come progetto dimostrativo all'interno di una rubrica di divulgazione su LinkedIn. Partendo da un caso pratico di organizzazione del lavoro, esploreremo passo dopo passo come raccogliere, organizzare, manipolare e interpretare i dati, fino a costruire analisi e strumenti sempre più evoluti.</p><p>L'obiettivo è raccontare in modo concreto quanto possa essere interessante leggere il mondo attraverso i dati: non soltanto numeri, ma domande, relazioni e storie da scoprire.</p><div class="bio-signature">Un progetto di Alessandro Marrazzo · Break&Go</div></div>""",unsafe_allow_html=True)


def render():
    st.set_page_config(page_title='Break&Go | Centro operativo',page_icon='☕',layout='wide',initial_sidebar_state='expanded')
    theme()
    st.sidebar.markdown('## ☕ Break&Go')
    st.sidebar.caption('DISTRIBUIAMO LE TUE PAUSE')
    import base64
    avatar_path=Path(__file__).resolve().parent.parent / 'assets' / 'alessandro_marrazzo.jpg'
    if avatar_path.is_file():
        avatar64=base64.b64encode(avatar_path.read_bytes()).decode('ascii')
        st.sidebar.markdown(f'<div class="bio-sidebar-author"><img src="data:image/jpeg;base64,{avatar64}" alt="Alessandro Marrazzo"><div><strong>Alessandro Marrazzo</strong><small>Autore di Break&Go</small></div></div>',unsafe_allow_html=True)
    if st.sidebar.button('Scopri la mia biografia →',key='sidebar_author_bio',use_container_width=True):
        navigate_to('Bio')
        st.rerun()
    st.sidebar.divider()
    pages=['Home','Tecnici','Flotta','Clienti e postazioni','Appuntamenti','Programmazione giornata','Analisi giornata lavorativa','Bio']
    icons=['⌂','👥','🚐','📍','📅','🗓️','🗺️','👤']
    if st.session_state.get('nav_page') not in pages:st.session_state['nav_page']='Home'
    page=st.sidebar.radio('Navigazione',pages,key='nav_page',format_func=lambda x: f'{icons[pages.index(x)]}   {x}')
    st.sidebar.divider()
    st.sidebar.caption('Snack · Caffè · Manutenzione')
    if page=='Home':home()
    elif page=='Flotta':hero('La flotta Break&Go','Gestisci i furgoni Ducato dei rifornitori e lo Scudo della manutenzione.');registry('flotta')
    elif page=='Tecnici':hero('Squadra e ruoli','Due squadre, due competenze: rifornimento e manutenzione.');registry('tecnici')
    elif page=='Clienti e postazioni':hero('Punti ristoro','Anagrafica dei clienti e dei distributori automatici.');registry('clienti')
    elif page=='Appuntamenti':hero('Agenda interventi','Importa o registra rifornimenti e manutenzioni, con finestre orarie e durata prevista.');registry('interventi')
    elif page=='Programmazione giornata':planning()
    elif page=='Analisi giornata lavorativa':work_analysis()
    elif page=='Bio':bio_page()
