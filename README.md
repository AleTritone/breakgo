# Break&Go - Pianificazione stradale gratuita

App Streamlit per pianificazione interventi e rifornimenti.

La geocodifica avviene tramite Nominatim (OpenStreetMap), con cache SQLite e intervallo tra le richieste. La matrice tempi/distanze e le geometrie dei percorsi provengono dal server pubblico OSRM. Non occorrono chiavi API.

## Avvio su Windows

```bat
cd /d "C:\Users\alessandro.marrazzo\Documents\Progetti Python\breakgo_project"
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m streamlit run app.py
```

**Conservare il database SQLite già presente.** Inserire indirizzi completi senza coordinate. La stima usa la rete stradale, non il traffico in tempo reale.

L'accesso ai server pubblici non è garantito e il loro uso è limitato: questa configurazione è indicata per dimostrazioni e test occasionali, non per carichi aziendali continuativi.
