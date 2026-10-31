# SEZIONE: Moduli guidati e selettori anagrafici
from datetime import date, datetime, time
import re
import pandas as pd
import streamlit as st
from .schema import TABLES, LABELS, KEYS
from .store import read, replace, validate
from .excel import workbook, read_upload


def next_id(table):
    prefix={'tecnici':'T','flotta':'V','clienti':'C','interventi':'I','magazzino':'R'}[table]
    existing=read(table)
    values=existing[KEYS[table]].astype(str).tolist()
    nums=[int(x[len(prefix):]) for x in values if re.fullmatch(re.escape(prefix)+r'\d+',x)]
    candidate=max(nums,default=0)+1
    while f'{prefix}{candidate:04d}' in values:
        candidate+=1
    return f'{prefix}{candidate:04d}'


def choices(table):
    df=read(table)
    if table=='tecnici':
        return {r.tecnico_id:f'{r.nome} {r.cognome} · {r.ruolo}' for _,r in df.iterrows()}
    if table=='flotta':
        return {r.mezzo_id:f'{r.targa} · {r.marca} {r.modello}' for _,r in df.iterrows()}
    if table=='clienti':
        return {r.cliente_id:f'{r.ragione_sociale} · {r.indirizzo}' for _,r in df.iterrows()}
    return {}


def selector(label, items, current='', key=None, empty='Seleziona...'):
    values=['']+list(items)
    index=values.index(str(current)) if str(current) in values else 0
    return st.selectbox(label,values,index=index,format_func=lambda x:items.get(x,empty) if x else empty,key=key)


def text_field(label,row,col,placeholder='',required=False):
    return st.text_input(label,value=str(row.get(col,'')),placeholder=placeholder,key=f'{st.session_state.get("_form_scope","new")}_{col}',help='Campo obbligatorio' if required else None).strip()


def number_field(label,row,col,default=0,min_value=0):
    try: value=int(float(row.get(col) or default))
    except (ValueError,TypeError): value=default
    return str(st.number_input(label,min_value=min_value,value=max(min_value,value),step=5 if 'durata' in col else 1,key=f'{st.session_state.get("_form_scope","new")}_{col}'))


def date_field(label,row,col):
    try: value=date.fromisoformat(str(row.get(col,''))[:10])
    except ValueError:value=date.today()
    return st.date_input(label,value=value,format='DD/MM/YYYY',key=f'{st.session_state.get("_form_scope","new")}_{col}').isoformat()


def time_field(label,row,col,default):
    raw=str(row.get(col,'') or default)
    try: value=datetime.strptime(raw[:5],'%H:%M').time()
    except ValueError:value=datetime.strptime(default,'%H:%M').time()
    return st.time_input(label,value=value,step=900,key=f'{st.session_state.get("_form_scope","new")}_{col}').strftime('%H:%M')


def yes_no(label,row,col):
    return st.selectbox(label,['si','no'],index=0 if str(row.get(col,'si')).lower() not in ('no','false','0') else 1,key=f'{st.session_state.get("_form_scope","new")}_{col}')


def select_static(label,row,col,options):
    val=str(row.get(col,options[0]))
    return st.selectbox(label,options,index=options.index(val) if val in options else 0,key=f'{st.session_state.get("_form_scope","new")}_{col}')


def build_fields(table,row):
    v={}
    if table=='flotta':
        a,b=st.columns(2)
        with a:
            v['targa']=text_field('Targa',row,'targa','AB123CD',True)
            v['marca']=text_field('Marca',row,'marca','Fiat')
            v['categoria']=select_static('Utilizzo',row,'categoria',['Rifornimento','Manutenzione'])
        with b:
            v['modello']=text_field('Modello',row,'modello','Ducato / Scudo')
            v['attivo']=yes_no('Mezzo disponibile',row,'attivo')
    elif table=='tecnici':
        a,b=st.columns(2)
        with a:
            v['nome']=text_field('Nome',row,'nome',required=True)
            v['ruolo']=select_static('Mansione',row,'ruolo',['Rifornimento','Manutenzione'])
            v['indirizzo_partenza']=text_field('Indirizzo di partenza',row,'indirizzo_partenza','Via, numero, città')
            v['inizio']=time_field('Inizio turno',row,'inizio','08:00')
            v['attivo']=yes_no('Tecnico attivo',row,'attivo')
        with b:
            v['cognome']=text_field('Cognome',row,'cognome',required=True)
            v['mezzo_id']=selector('Furgone assegnato',choices('flotta'),row.get('mezzo_id',''),key=f'{st.session_state.get("_form_scope","new")}_mezzo_id',empty='Nessun furgone')
            v['fine']=time_field('Fine turno',row,'fine','17:00')
        v['lat']=str(row.get('lat',''));v['lon']=str(row.get('lon',''))
    elif table=='clienti':
        v['ragione_sociale']=text_field('Nome cliente / punto ristoro',row,'ragione_sociale','Es. Uffici Milano Nord',True)
        v['indirizzo']=text_field('Indirizzo completo',row,'indirizzo','Via, numero civico, 20100 Milano',True)
        v['tipo_macchina']=select_static('Distributori presenti',row,'tipo_macchina',['Snack + Caffè','Snack','Caffè','Bevande','Snack + Bevande','Altro'])
        v['note']=st.text_area('Note',value=str(row.get('note','')),key=f'{st.session_state.get("_form_scope","new")}_note')
        v['lat']=str(row.get('lat',''));v['lon']=str(row.get('lon',''))
    elif table=='interventi':
        a,b=st.columns(2)
        with a:
            v['data']=date_field('Data intervento',row,'data')
            v['cliente_id']=selector('Cliente / punto ristoro',choices('clienti'),row.get('cliente_id',''),key=f'{st.session_state.get("_form_scope","new")}_cliente_id')
            v['durata_min']=number_field('Durata intervento (minuti)',row,'durata_min',25)
            v['fascia_inizio']=time_field('Fascia dalle',row,'fascia_inizio','08:00')
        with b:
            v['tipo']=select_static('Tipo di intervento',row,'tipo',['Rifornimento','Manutenzione'])
            v['priorita']=select_static('Priorità',row,'priorita',['Normale','Alta','Urgente','Bassa'])
            v['fascia_fine']=time_field('Fascia alle',row,'fascia_fine','18:00')
        v['note']=st.text_area('Istruzioni per il tecnico',value=str(row.get('note','')),key=f'{st.session_state.get("_form_scope","new")}_note')
    return v


def save_record(table,values,record_id=None):
    df=read(table)
    key=KEYS[table]
    values[key]=record_id or next_id(table)
    if table=='tecnici' and (not values['nome'] or not values['cognome']):
        raise ValueError('Nome e cognome sono obbligatori.')
    if table=='flotta' and not values['targa']:
        raise ValueError('La targa è obbligatoria.')
    if table=='clienti' and (not values['ragione_sociale'] or not values['indirizzo']):
        raise ValueError('Inserisci il nome del cliente e un indirizzo completo.')
    if table=='interventi' and not values['cliente_id']:
        raise ValueError('Seleziona un punto ristoro.')
    if table=='interventi' and values['fascia_fine']<=values['fascia_inizio']:
        raise ValueError('La fine della fascia deve essere successiva all’inizio.')
    if table=='clienti' and record_id:
        old=df.loc[df[key]==record_id]
        if len(old) and str(old.iloc[0]['indirizzo'])!=values['indirizzo']:
            values['lat']='';values['lon']=''
    if table=='tecnici' and record_id:
        old=df.loc[df[key]==record_id]
        if len(old) and str(old.iloc[0]['indirizzo_partenza'])!=values['indirizzo_partenza']:
            values['lat']='';values['lon']=''
    if record_id:
        df=df[df[key]!=record_id]
    new=pd.DataFrame([values],columns=TABLES[table]).fillna('')
    clean=validate(table,pd.concat([df,new],ignore_index=True))
    replace(table,clean)


def delete_record(table,record_id):
    key=KEYS[table]
    if table=='clienti' and record_id in set(read('interventi').cliente_id):
        raise ValueError('Cliente collegato ad appuntamenti: elimina prima gli appuntamenti.')
    if table=='flotta' and record_id in set(read('tecnici').mezzo_id):
        raise ValueError('Furgone assegnato a un tecnico: cambia prima l’assegnazione.')
    if table=='tecnici' and (record_id in set(read('presenze').tecnico_id) or record_id in set(read('magazzino').tecnico_id)):
        raise ValueError('Tecnico collegato a presenze o ritiri: elimina prima i collegamenti.')
    df=read(table)
    replace(table,df[df[key]!=record_id])


def import_export(table):
    with st.expander('Importazione Excel ed esportazione',expanded=False):
        st.caption('L’importazione sostituisce i dati della sezione. Esporta prima una copia se vuoi conservarli.')
        st.download_button('Scarica modello Excel',workbook({table:pd.DataFrame(columns=TABLES[table])}),file_name=f'modello_{table}.xlsx',key=f'model_{table}')
        uploaded=st.file_uploader('Carica Excel',type=['xlsx'],key=f'upload_{table}')
        if uploaded is not None and st.button('Importa e sostituisci',key=f'import_{table}'):
            try:
                replace(table,validate(table,read_upload(uploaded,table)))
                st.success('Importazione completata.');st.rerun()
            except Exception as exc:st.error(str(exc))
        st.download_button('Esporta dati attuali',workbook({table:read(table)}),file_name=f'breakgo_{table}.xlsx',key=f'export_{table}')


def registry(table):
    st.subheader(LABELS[table])
    df=read(table)
    key=KEYS[table]
    import_export(table)
    st.subheader(f'Elenco {LABELS[table].lower()} · {len(df)}')
    if df.empty:st.info('Nessun elemento registrato.')
    else:
        display=df.copy()
        if table=='tecnici':display['Furgone']=display.mezzo_id.map(choices('flotta')).fillna('Non assegnato');display=display[['nome','cognome','ruolo','Furgone','inizio','fine','attivo']]
        if table=='interventi':display=display.sort_values(['data','fascia_inizio','fascia_fine'],kind='stable');display['Cliente']=display.cliente_id.map(choices('clienti')).fillna(display.cliente_id);display=display[['data','Cliente','tipo','durata_min','fascia_inizio','fascia_fine','priorita']]
        if table=='clienti':display=display[['ragione_sociale','indirizzo','tipo_macchina','note']]
        if table=='flotta':display=display[['targa','marca','modello','categoria','attivo']]
        st.dataframe(display,hide_index=True,use_container_width=True,height=min(530,90+len(df)*35))


    st.divider()
    st.markdown('#### Inserimento e modifica guidati')
    mode_key=f'{table}_mode'
    if st.session_state.get(mode_key) not in ('Nuovo','Modifica esistente'):
        st.session_state[mode_key]='Nuovo'
    left,right=st.columns(2,gap='small')
    with left:
        if st.button('＋  Nuovo',key=f'{table}_new_button',type='primary' if st.session_state[mode_key]=='Nuovo' else 'secondary',use_container_width=True):
            st.session_state[mode_key]='Nuovo'
            st.rerun()
    with right:
        if st.button('✎  Modifica esistente',key=f'{table}_edit_button',type='primary' if st.session_state[mode_key]=='Modifica esistente' else 'secondary',use_container_width=True):
            st.session_state[mode_key]='Modifica esistente'
            st.rerun()
    mode=st.session_state[mode_key]
    selected=None
    if mode=='Modifica esistente':
        if df.empty:
            st.info('Nessun elemento registrato. Usa Nuovo per aggiungerne uno.');return
        if table=='interventi':
            clients=choices('clienti')
            labels={r[key]:f'{r.data} · {clients.get(r.cliente_id,r.cliente_id)} · {r.tipo}' for _,r in df.iterrows()}
        else:
            labels=choices(table)
        selected=st.selectbox('Seleziona elemento da modificare',df[key].tolist(),format_func=lambda x:labels.get(x,x),key=f'{table}_edit_select')
    row=df.loc[df[key]==selected].iloc[0].to_dict() if selected else {}
    st.session_state['_form_scope']=f'{table}_{selected or "new"}'
    with st.form(f'form_{table}_{selected or "new"}',clear_on_submit=False):
        values=build_fields(table,row)
        submitted=st.form_submit_button('Salva modifiche' if selected else 'Aggiungi',type='primary',use_container_width=True)
    if submitted:
        try:
            save_record(table,values,selected)
            st.success('Dati salvati correttamente.');st.rerun()
        except Exception as exc:st.error(str(exc))
    if selected:
        with st.expander('Elimina elemento'):
            st.warning('L’eliminazione è definitiva.')
            if st.button('Conferma eliminazione',key=f'delete_{table}_{selected}'):
                try:delete_record(table,selected);st.rerun()
                except Exception as exc:st.error(str(exc))

def warehouse_form(day):
    st.subheader('Passaggi in magazzino')
    st.caption('Aggiungi un passaggio alla volta. Il codice viene creato automaticamente e il tecnico si sceglie dal menu.')
    tech=choices('tecnici')
    all_rows=read('magazzino')
    today=all_rows[all_rows.data==day]
    if not tech:
        st.info('Registra prima i tecnici.');return
    with st.form(f'new_warehouse_{day}'):
        a,b=st.columns(2)
        with a:
            tid=selector('Tecnico',tech,key='warehouse_tech')
            known=sorted(set(x for x in all_rows.indirizzo.tolist() if x.strip()))
            address_mode=st.selectbox('Sede di magazzino',['Nuovo indirizzo']+known)
            address=st.text_input('Indirizzo completo',placeholder='Via, civico, città') if address_mode=='Nuovo indirizzo' else address_mode
            start=st.time_input('Disponibile dalle',value=time(11,30),step=900)
        with b:
            duration=st.number_input('Durata carico (minuti)',min_value=5,value=20,step=5)
            end=st.time_input('Disponibile fino alle',value=time(14,30),step=900)
        submitted=st.form_submit_button('Aggiungi passaggio',type='primary')
    if submitted:
        try:
            if not tid:raise ValueError('Seleziona un tecnico.')
            if not address.strip():raise ValueError('Inserisci l’indirizzo del magazzino.')
            if end<=start:raise ValueError('La fine della fascia deve essere successiva all’inizio.')
            values={'ritiro_id':next_id('magazzino'),'data':day,'tecnico_id':tid,'indirizzo':address.strip(),'lat':'','lon':'','fascia_inizio':start.strftime('%H:%M'),'fascia_fine':end.strftime('%H:%M'),'durata_min':str(duration)}
            replace('magazzino',validate('magazzino',pd.concat([all_rows,pd.DataFrame([values])],ignore_index=True)))
            st.success('Passaggio aggiunto.');st.rerun()
        except Exception as exc:st.error(str(exc))
    if today.empty:
        st.info('Nessun passaggio previsto per questa giornata.')
    else:
        view=today.copy()
        view['Tecnico']=view.tecnico_id.map(tech).fillna(view.tecnico_id)
        st.dataframe(view[['Tecnico','indirizzo','fascia_inizio','fascia_fine','durata_min']],hide_index=True,use_container_width=True)
        labels={r.ritiro_id:f'{tech.get(r.tecnico_id,r.tecnico_id)} · {r.fascia_inizio}-{r.fascia_fine} · {r.indirizzo}' for _,r in today.iterrows()}
        selected=st.selectbox('Passaggio da eliminare',list(labels),format_func=lambda x:labels[x])
        if st.button('Elimina passaggio selezionato'):
            replace('magazzino',all_rows[all_rows.ritiro_id!=selected]);st.rerun()
