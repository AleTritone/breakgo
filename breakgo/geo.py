# SEZIONE: Geocodifica e routing stradale OpenStreetMap
import math
import sqlite3
import time
import requests
from .store import connect

NOMINATIM = 'https://nominatim.openstreetmap.org/search'
OSRM = 'https://router.project-osrm.org'
HEADERS = {'User-Agent': 'BreakGoLocalDemo/1.0 (Streamlit local demo)', 'Accept': 'application/json'}
PHOTON = 'https://photon.komoot.io/api/'
_last_geocode = 0.0


def minutes(value):
    try:
        dt = __import__('pandas').to_datetime(str(value), errors='raise')
        return dt.hour * 60 + dt.minute
    except Exception as exc:
        raise ValueError(f'Orario non valido: {value} (usare HH:MM)') from exc


def coordinate(address, lat=None, lon=None):
    global _last_geocode
    address = str(address).strip()
    if not address:
        raise ValueError('Indirizzo mancante')
    with connect() as db:
        db.execute('CREATE TABLE IF NOT EXISTS geo_cache (address TEXT PRIMARY KEY, lat REAL, lon REAL)')
        cached = db.execute('SELECT lat,lon FROM geo_cache WHERE address=?', (address,)).fetchone()
    if cached:
        return float(cached[0]), float(cached[1])
    wait = 1.1 - (time.monotonic() - _last_geocode)
    if wait > 0:
        time.sleep(wait)
    errors = []
    result = None
    try:
        response = requests.get(NOMINATIM, params={'q': address, 'format': 'json', 'limit': 1, 'countrycodes': 'it'}, headers=HEADERS, timeout=20)
        _last_geocode = time.monotonic()
        response.raise_for_status()
        found = response.json()
        if found:
            result = float(found[0]['lat']), float(found[0]['lon'])
        else:
            errors.append('Nominatim: indirizzo non trovato')
    except (requests.RequestException, ValueError, KeyError, IndexError) as exc:
        errors.append(f'Nominatim: {exc}')
    if result is None:
        wait = 1.1 - (time.monotonic() - _last_geocode)
        if wait > 0:
            time.sleep(wait)
        try:
            response = requests.get(PHOTON, params={'q': address, 'limit': 5, 'lang': 'it'}, headers=HEADERS, timeout=25)
            _last_geocode = time.monotonic()
            response.raise_for_status()
            features = response.json().get('features', [])
            italian = [f for f in features if str(f.get('properties', {}).get('countrycode', '')).lower() == 'it']
            matches = italian or features
            if matches:
                lon, lat = matches[0]['geometry']['coordinates'][:2]
                result = float(lat), float(lon)
            else:
                errors.append('Photon: indirizzo non trovato')
        except (requests.RequestException, ValueError, KeyError, IndexError, TypeError) as exc:
            errors.append(f'Photon: {exc}')
    if result is None:
        raise ValueError(f'Impossibile geocodificare {address}. ' + ' | '.join(errors) + '. Verificare connessione, disponibilita dei servizi e indirizzo.')
    with connect() as db:
        db.execute('INSERT OR REPLACE INTO geo_cache (address,lat,lon) VALUES (?,?,?)', (address, *result))
    return result


def _request(path, params=None, timeout=90):
    try:
        response = requests.get(OSRM + path, params=params, headers=HEADERS, timeout=timeout)
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise ValueError('Servizio stradale OSRM temporaneamente non disponibile. Riprova più tardi.') from exc
    if data.get('code') != 'Ok':
        raise ValueError('OSRM non ha trovato un percorso stradale: ' + str(data.get('message', data.get('code'))))
    return data


def _locations(coords):
    return ';'.join(f'{float(lon):.6f},{float(lat):.6f}' for lat, lon in coords)


def matrix(coords, speed=None):
    if not coords:
        raise ValueError('Nessun indirizzo da ottimizzare.')
    if len(coords) > 50:
        raise ValueError('La demo supporta fino a 50 località distinte per pianificazione, per limitare le richieste al server pubblico OSRM.')
    data = _request('/table/v1/driving/' + _locations(coords), {'annotations': 'duration,distance'}, timeout=120)
    distances, durations = data.get('distances'), data.get('durations')
    if distances is None or durations is None or any(value is None for row in distances for value in row) or any(value is None for row in durations for value in row):
        raise ValueError('Alcune località non risultano collegate dalla rete stradale.')
    return [[round(value / 1000, 3) for value in row] for row in distances], [[math.ceil(value / 60) for value in row] for row in durations], 'stradale OSRM / OpenStreetMap (senza traffico live)'


def road_geometry(stops):
    if len(stops) < 2:
        return [[float(stop['lat']), float(stop['lon'])] for stop in stops]
    coords = [(float(stop['lat']), float(stop['lon'])) for stop in stops]
    if len(set(coords)) == 1:
        return [[lat, lon] for lat, lon in coords]
    data = _request('/route/v1/driving/' + _locations(coords), {'overview': 'full', 'geometries': 'geojson', 'steps': 'false'}, timeout=120)
    routes = data.get('routes') or []
    if not routes:
        raise ValueError('Impossibile disegnare il percorso stradale selezionato.')
    return [[lat, lon] for lon, lat in routes[0]['geometry']['coordinates']]
