# Nokia FastMile 5G Home Assistant Integration

Ta dokumentacja opisuje integrację `nokia_fastmile` dla Home Assistant, która umożliwia pobieranie stanu i statystyk z routera Nokia FastMile 5G14-B.

## Instalacja

1. Umieść katalog `custom_components/nokia_fastmile` w katalogu `custom_components` swojej instalacji Home Assistant.
2. Jeżeli instalujesz ręcznie, umieść plik `www/nokia-fastmile-card.js` w katalogu `www` swojej instalacji Home Assistant. Przy instalacji przez HACS użyj adresu karty serwowanego przez integrację.
3. Dodaj do `configuration.yaml`:
   ```yaml
   frontend:
     extra_module_url:
      - /nokia_fastmile/nokia-fastmile-card.js?v=1.0.23
   ```
4. Zrestartuj Home Assistant.
5. Przejdź do `Ustawienia > Urządzenia i usługi > Dodaj integrację` i wyszukaj `Nokia FastMile 5G`.

## Konfiguracja karty Lovelace

Po zainstalowaniu integracji możesz dodać kartę do dashboardu:

1. Edytuj dashboard w trybie YAML lub wizualnym.
2. Dodaj nową kartę typu `custom:nokia-fastmile-card`.
3. Opcjonalnie skonfiguruj `entity` (domyślnie `sensor.nokia_fastmile_5g_connection_state`).

Przykład konfiguracji YAML:
```yaml
type: custom:nokia-fastmile-card
entity: sensor.nokia_fastmile_5g_connection_state
```

## Konfiguracja integracji

Podczas dodawania integracji podaj:

- **Adres IP routera**: domyślnie `192.168.192.1`
- **Nazwa użytkownika**: domyślnie `admin`
- **Hasło**: hasło administratora routera
- **Użyj HTTPS**: wyłączone (HTTP)

### Uwaga
Router Nokia FastMile w tym repozytorium komunikuje się z panelem webowym pod adresem:
- `http://192.168.192.1`

Jeżeli widzisz panel routera w przeglądarce pod innym adresem, użyj tego adresu w konfiguracji integracji.

## Jak działa logowanie

Integracja używa protokołu logowania specyficznego dla Nokii:

1. GET `/login_web_app.cgi?nonce`
2. GET `/login_web_app.cgi?salt`
3. POST `/login_web_app.cgi` z zakodowanymi hasłami

Poprawka w kodzie uwzględnia zarówno status HTTP `200`, jak i `299` jako sukces logowania, ponieważ router może zwracać jedną z tych odpowiedzi.

## Diagnostyka

Jeżeli konfiguracja nie działa:

- sprawdź, czy router jest dostępny z sieci lokalnej
- otwórz w przeglądarce `http://192.168.192.1`
- jeśli strona działa, użyj tego adresu w konfiguracji
- włącz debugowanie loggera dla integracji dodając do `configuration.yaml`:
  ```yaml
  logger:
    logs:
      custom_components.nokia_fastmile: debug
  ```
- po restarcie HA znajdź w logach wpisy zaczynające się od `nokia_fastmile config:` lub `nokia_fastmile:`.

## Typowe błędy

- `cannot_connect` — brak połączenia z routerem lub błędny adres IP
- `invalid_auth` — nieprawidłowy login/hasło
- `unknown` — nieoczekiwany błąd podczas próby logowania

## Pliki integracji

- `custom_components/nokia_fastmile/config_flow.py` — logika konfiguracji i test logowania
- `custom_components/nokia_fastmile/coordinator.py` — pobieranie danych i uwierzytelnianie
- `custom_components/nokia_fastmile/const.py` — stałe, adresy ścieżek i konfiguracja
- `custom_components/nokia_fastmile/manifest.json` — metadane integracji
- `www/nokia-fastmile-card.js` — karta Lovelace do wizualizacji danych

## Statystyki transferu

Sensory `Cellular Bytes Received`, `Cellular Bytes Sent`, `Ethernet Bytes Received`,
`Ethernet Bytes Sent`, `Ethernet Packets Received` i `Ethernet Packets Sent`
są pobierane z endpointu:

- `/status_get_web_app.cgi`

Jeżeli ten endpoint nie odpowie poprawnie, integracja pominie tylko statystyki
transferu i nadal zaktualizuje podstawowe dane 5G/LTE oraz informacje o urządzeniu.

## Restart routera

Integracja udostępnia encję `button` o nazwie `Restart router` przy urządzeniu
Nokia FastMile. Jej naciśnięcie wysyła do routera żądanie restartu z aktywnej,
uwierzytelnionej sesji. W trakcie restartu sensory mogą być przez chwilę
niedostępne.

Przykładowa natywna karta Lovelace, niewymagająca dodatkowego zasobu JavaScript:

```yaml
type: button
entity: button.nokia_fastmile_5g_restart_router
name: Restart router
icon: mdi:restart
tap_action:
  action: call-service
  service: button.press
  target:
    entity_id: button.nokia_fastmile_5g_restart_router
  confirmation:
    text: Czy na pewno zrestartować router Nokia FastMile?
```

## Dodatkowe dane

Od wersji `1.0.5` integracja probuje uzupelniac brakujace liczniki transferu z
`/statistics_status_web_app.cgi`, gdy `/status_get_web_app.cgi` nie zwroci
wszystkich pol.

Dodatkowo pobierane sa pola radiowe i sieciowe: `5G Band`, `5G Downlink ARFCN`,
`LTE Band`, `LTE Downlink EARFCN`, `APN`, `Cellular Connection State` oraz
`Ethernet Status`.

## Wersja

Aktualnie obsługiwana wersja firmware routera: `1.2302.00.0355`.
