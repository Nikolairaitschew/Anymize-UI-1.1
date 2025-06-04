# NocoDB Job Table API – Endpunkt-Dokumentation

## Basis-URL
`/api/v2/tables/mun2eil6g6a3i25/records`

---

## Endpunkte

### 1. Job List (Alle Jobs auflisten)
**GET** `/api/v2/tables/mun2eil6g6a3i25/records`
- Listet alle Zeilen aus der Job-Tabelle.
- **Query-Parameter:**
  - `viewId` (string): Filter nach View
  - `fields` (string): Felder, die zurückgegeben werden
  - `sort` (string): Sortierreihenfolge
  - `where` (string): Filterbedingung, z.B. `where=(field1,eq,value)`
  - `limit`, `offset`, `shuffle`: Pagination
  - `nested[user][fields]`: Felder im verschachtelten User-Objekt
- **Antwort:**
  - JSON mit `list` (Array der Jobs) und `PageInfo`

### 2. Job Create (Neuen Job anlegen)
**POST** `/api/v2/tables/mun2eil6g6a3i25/records`
- Fügt einen neuen Job ein.
- **Body:** JSON mit Feldern wie `internal_ID`, `input_text`, `output_text`
- **Antwort:**
  - JSON mit allen Feldern des neuen Datensatzes inkl. `Id` (Primärschlüssel)

### 3. Job Update (Teilweise aktualisieren)
**PATCH** `/api/v2/tables/mun2eil6g6a3i25/records`
- Aktualisiert Felder eines Jobs.
- **Body:** JSON mit zu aktualisierenden Feldern
- **Antwort:**
  - JSON-String mit Bestätigung

### 4. Job Delete (Löschen via Primärschlüssel)
**DELETE** `/api/v2/tables/mun2eil6g6a3i25/records`
- Löscht einen Datensatz per Primärschlüssel.
- **Body:** `{ "Id": <int> }`
- **Antwort:**
  - `200 OK`

### 5. Job Read (Einzelnen Job abrufen via Primärschlüssel)
**GET** `/api/v2/tables/mun2eil6g6a3i25/records/{recordId}`
- Holt einen Datensatz per Primärschlüssel (`Id`).
- **Pfad-Parameter:**
  - `recordId` (int): Primärschlüssel des Jobs
  - Optional: `fields` (string): Felder, die zurückgegeben werden
- **Antwort:**
  - JSON mit allen Feldern des Jobs

### 6. Job Count (Anzahl der Jobs)
**GET** `/api/v2/tables/mun2eil6g6a3i25/records/count`
- Gibt die Anzahl der Datensätze zurück (optional gefiltert).
- **Query-Parameter:**
  - `where` (string): Filterbedingung
  - `viewId` (string): View-Filter
- **Antwort:** `{ "count": <int> }`

### 7. Link Records List (Verknüpfte Records abrufen)
**GET** `/api/v2/tables/mun2eil6g6a3i25/links/{linkFieldId}/records/{recordId}`
- Holt verknüpfte Records für ein Link-Feld und eine Record-Id.
- **Pfad-Parameter:**
  - `linkFieldId` (string): z.B. `cp2ruywux9sa86i` (user), `calbadm3zmtag36` (chat_memories)
  - `recordId` (int): Primärschlüssel des Jobs
- **Antwort:**
  - JSON mit `list` (Array der verknüpften Records)

### 8. Link Records (Verknüpfen)
**POST** `/api/v2/tables/mun2eil6g6a3i25/links/{linkFieldId}/records/{recordId}`
- Verknüpft Records mit einem Link-Feld.
- **Body:** Array von Record-Ids
- **Antwort:**
  - `true` bei Erfolg

### 9. Unlink Records (Verknüpfung aufheben)
**DELETE** `/api/v2/tables/mun2eil6g6a3i25/links/{linkFieldId}/records/{recordId}`
- Hebt Verknüpfungen auf.
- **Body:** Array von Record-Ids
- **Antwort:**
  - `true` bei Erfolg

---

## Felder der Job-Tabelle (laut Beispiel)
- `Id` (int, Primärschlüssel)
- `internal_ID` (string)
- `user_id` (int)
- `user` (Objekt: first_name, last_name, email)
- `file` (Array: mimetype, size, title, url, icon)
- `input_text` (string)
- `output_text` (string)
- `chat_memories` (int)

---

**Hinweis:**
- Die Abfrage nach einem bestimmten Job über ein beliebiges Feld (z.B. `job_id`) ist nur über den List-Endpunkt mit einem passenden `where`-Parameter möglich, z.B.:
  - `/api/v2/tables/mun2eil6g6a3i25/records?where=(job_id,eq,12345)`
- Der Endpunkt `/records/{recordId}` funktioniert nur mit dem Primärschlüssel `Id`.
