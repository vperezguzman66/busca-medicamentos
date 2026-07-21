# BuscaMedicamentos

Aplicación web para comparar precios de medicamentos en las principales farmacias de cadena de Chile: **SalcoBrand**, **Cruz Verde**, **Farmacias Ahumada** y **Doctor Simi**.

## Características

- **Búsqueda simple** — escribe un medicamento y obtén resultados de todas las farmacias en paralelo, ordenados de menor a mayor precio
- **Promociones y descuentos** — cuando una farmacia muestra un precio rebajado, se ve el % de descuento y el precio normal tachado
- **Búsqueda en lote (CSV)** — sube un archivo con hasta 30 medicamentos; los resultados llegan en tiempo real con barra de progreso
- **Exportar a CSV** — descarga los resultados en formato compatible con Excel (con BOM para acentos)
- **Filtro por farmacia** — selecciona en qué farmacias buscar
- **Historial de búsquedas** — las últimas 10 búsquedas se guardan en el navegador como accesos rápidos
- **Caché de resultados** — búsquedas repetidas son instantáneas (caché en memoria de 5 minutos)

## Requisitos

- Python 3.11 o superior
- Conexión a internet

## Instalación y uso

```bash
cd busca-medicamentos
./run.sh
```

El script crea el entorno virtual, instala dependencias (incluyendo Chromium para Playwright, usado solo por Cruz Verde) y levanta el servidor. Abre `http://localhost:8000` en el navegador.

Para detener el servidor: `Ctrl+C`

## Estructura del proyecto

```
busca-medicamentos/
├── backend/
│   ├── main.py               # API FastAPI (arranca/cierra el browser de Playwright vía lifespan)
│   ├── requirements.txt
│   └── scrapers/
│       ├── base.py           # Dataclass Product, clase base BaseScraper, format_clp_price()
│       ├── salcobrand.py     # Scraper SalcoBrand (API Algolia)
│       ├── ahumada.py        # Scraper Farmacias Ahumada (HTML server-rendered)
│       ├── drsimi.py         # Scraper Doctor Simi (API VTEX)
│       └── cruzverde.py      # Scraper Cruz Verde (Playwright)
├── frontend/
│   ├── index.html
│   ├── style.css
│   └── app.js
└── run.sh
```

## API

El backend expone una API REST en `http://localhost:8000`:

- `GET /api/search?query={q}&stores={ids}&max_results={n}` — búsqueda simple. A diferencia de `buscaprecios`, responde como **Server-Sent Events**: cada farmacia que termina emite un evento con el snapshot acumulado de resultados (ordenado y con `pending` = farmacias que aún faltan), en vez de esperar a que las 4 terminen. Como Cruz Verde (Playwright) es mucho más lenta que las otras 3, esto evita que una búsqueda que podría mostrarse en ~1s quede bloqueada ~13s esperándola (rate limit 20/min)
- `POST /api/search-batch` — búsqueda en lote vía CSV, respuesta como Server-Sent Events, un evento por medicamento del lote (rate limit 5/min)
- `GET /api/stores` — lista de farmacias disponibles

## Cómo funciona cada scraper

### SalcoBrand

SalcoBrand corre sobre Spree Commerce, pero el buscador del sitio usa **Algolia**. El App ID y la API key (de solo lectura, restringida por `Referer`) están embebidos en el bundle público `search_bar-*.js` del propio sitio — no son secretos del proyecto, son la misma key que usa el navegador de cualquier visitante.

- **Búsqueda:** `POST https://GM3RP06HJG-dsn.algolia.net/1/indexes/sb_variant_production/query` con header `Referer: https://salcobrand.cl/`
- **Precio:** `direct_discount` si existe (precio con descuento directo), si no `normal_price`
- **URL del producto:** `https://salcobrand.cl/products/{slug}`
- El analizador de Algolia devuelve 0 resultados para cualquier query con `/`, así que dosis combinadas como "colmibe 40/10" nunca calzaban con nada. Se normaliza cada lado como su propio token `mg` (`40mg 10mg`) antes de buscar.

### Farmacias Ahumada

Ahumada corre sobre Salesforce Commerce Cloud (Demandware). La página de búsqueda es **server-rendered**: cada resultado es un bloque HTML con `data-pid="{sku}"`, sin necesidad de JavaScript.

- **Búsqueda:** `GET https://www.farmaciasahumada.cl/search?q={query}`
- **Precio:** no viene en un atributo limpio — el precio vigente solo aparece como texto plano (`$X.XXX`) dentro de `span.sales`; el precio de lista/tachado sí trae un atributo `content` limpio dentro de `<del>`. Se parsea con BeautifulSoup extrayendo el primer monto en `span.sales`.

### Doctor Simi

El dominio correcto es **`www.drsimi.cl`** (no `farmaciasdrsimi.cl`, que no resuelve). Corre sobre VTEX (cuenta `farmaciasdeldrsimicl`), con la API legacy de catálogo pública y sin autenticación.

- **Búsqueda:** `GET https://farmaciasdeldrsimicl.vtexcommercestable.com.br/api/catalog_system/pub/products/search/{query}?map=ft`. La forma clásica `?ft={query}` responde 400 ("Scripts are not allowed!") para cualquier búsqueda de 2+ palabras — es una regla del WAF, no un error de sintaxis. Pasar el término como segmento de la URL con `map=ft` evita el bloqueo.
- **Precio:** `items[0].sellers[0].commertialOffer.Price` (fallback a `ListPrice`)
- **URL del producto:** `https://www.drsimi.cl/{linkText}/p`

### Cruz Verde

Cruz Verde es una SPA Angular detrás de **Incapsula** (WAF), y su API pública (`api.cruzverde.cl/product-service/products/search`) exige una sesión obtenida vía un flow OAuth propio contra Andes ML/Keycloak — no es viable de replicar con `httpx` de forma confiable.

Este scraper usa **Playwright** (Chromium headless): navega a `https://www.cruzverde.cl/`, escribe en el buscador, espera los resultados renderizados y los parsea del DOM. A diferencia de un scraper `httpx`, no lanza un browser nuevo por cada búsqueda — la app mantiene **una sola instancia de Chromium compartida** (arrancada en el `lifespan` de FastAPI) y abre un `browser.new_context()` liviano por cada búsqueda.

- **Precio:** `p.text-green-turquoise` (precio vigente, verde y destacado); `p.line-through` cuando hay descuento (precio tachado, no usado actualmente)
- Es notoriamente más lento que las otras 3 tiendas (varios segundos por render de página completo), pero corre en paralelo con las demás gracias a `asyncio.gather`.

## Seguridad

Mismas medidas que `buscaprecios`: rate limiting (`slowapi`), CSP y headers de seguridad, CORS restringido a `localhost:8000`, límite de tamaño de CSV (100 KB), sanitización de URLs en el frontend, `rel="noopener noreferrer"` en links externos.

## Dependencias

| Paquete | Uso |
|---------|-----|
| `fastapi` | Framework API |
| `uvicorn` | Servidor ASGI |
| `httpx` | Cliente HTTP async (SalcoBrand, Ahumada, Doctor Simi) |
| `beautifulsoup4` | Parseo HTML (Ahumada) |
| `playwright` | Navegador headless (Cruz Verde) |
| `python-multipart` | Subida de archivos CSV |
| `slowapi` | Rate limiting por IP |

## Notas técnicas

- **Cruz Verde** es el más lento por naturaleza (render de página completa vía Chromium). Si su búsqueda falla o tarda demasiado en una consulta puntual, las demás farmacias igual devuelven resultados — los errores por tienda no interrumpen la búsqueda combinada.
- Los scrapers dependen de la estructura actual de cada sitio. Si una farmacia rediseña su plataforma (o cambia su proveedor de búsqueda/WAF), el scraper correspondiente puede necesitar ajustes.
- Este proyecto es solo un comparador informativo de precios públicos ya listados por cada farmacia — no gestiona compras, recetas ni datos de pacientes.
