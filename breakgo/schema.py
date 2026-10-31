# SEZIONE: Schema dati
TABLES = {
    'tecnici': ['tecnico_id','nome','cognome','ruolo','mezzo_id','indirizzo_partenza','lat','lon','inizio','fine','attivo'],
    'flotta': ['mezzo_id','targa','marca','modello','categoria','attivo'],
    'clienti': ['cliente_id','ragione_sociale','indirizzo','lat','lon','tipo_macchina','note'],
    'interventi': ['intervento_id','data','cliente_id','tipo','durata_min','fascia_inizio','fascia_fine','priorita','note'],
    'presenze': ['data','tecnico_id','presente'],
    'magazzino': ['ritiro_id','data','tecnico_id','indirizzo','lat','lon','fascia_inizio','fascia_fine','durata_min'],
}
LABELS = {'tecnici':'Tecnici','flotta':'Flotta','clienti':'Clienti e postazioni','interventi':'Appuntamenti','presenze':'Presenze giornaliere','magazzino':'Passaggi in magazzino'}
KEYS = {'tecnici':'tecnico_id','flotta':'mezzo_id','clienti':'cliente_id','interventi':'intervento_id','magazzino':'ritiro_id'}
ROLES = ['Rifornimento','Manutenzione']
TYPES = ['Rifornimento','Manutenzione']
