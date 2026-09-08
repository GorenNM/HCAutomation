# Guía reproducible — Diagramas tipo imagen (no-mermaid) por SVG generado

Método para que **cualquier agente** convierta un flowchart/ER de mermaid en una imagen
estilo documentación AWS / ER limpio (PNG + SVG editable), sin que "parezca IA".

No se usa el render nativo de mermaid ni un visualizador inline. Se genera **SVG a mano**
con un script Python parametrizado y se rasteriza a PNG. Esto da control total de layout,
íconos, paleta y tipografía, y produce un asset incrustable en documentación.

---

## 0. Resultado esperado

- `modelo-datos-mmn.svg` — vectorial, editable (texto/colores reales, no trazos).
- `modelo-datos-mmn.png` — rasterizado @2x para incrustar en docs/slides.
- Estilo: tarjetas con barra de acento por categoría, badges, bandas/agrupadores con borde
  punteado, flechas finas con marcador, leyenda con chips de color.

---

## 1. Cuándo usar este método

- El usuario pide una **imagen** de una arquitectura o modelo, "no formato mermaid",
  "que parezca documentación oficial".
- Se necesita un asset reutilizable (PNG para pegar, SVG para editar).
- El grafo es pequeño-mediano (≈5–25 nodos). Para grafos enormes, conviene un motor de
  layout (graphviz/elk); este método es manual y se controla por coordenadas.

No usar el visualizador inline cuando: prohíbe íconos dentro de cajas, limita ancho, o no
deja exportar archivo. Ese fue el caso aquí → por eso SVG a mano.

---

## 2. Decisión de diseño: por qué SVG a mano

| Opción | Problema |
|---|---|
| Render mermaid | Estética genérica "de IA", poco control de íconos/paleta, difícil incrustar |
| Visualizador inline | Sin íconos dentro de cajas, ancho limitado, no exporta archivo |
| **SVG generado + cairosvg** | Control total, salida vectorial + raster, incrustable, replicable |

SVG es texto: se compone por string-building en Python, se versiona y se diffea.
El PNG se obtiene rasterizando el mismo SVG (una sola fuente de verdad).

---

## 3. Entorno (comandos exactos)

Contenedor Linux con Python 3. Rasterizador:

```bash
pip install cairosvg --break-system-packages   # v2.9.0; trae cffi/cairocffi
```

> No asumas `rsvg-convert` ni `inkscape`: pueden no estar. `cairosvg` es la apuesta segura.

### Caveat de fuentes (importante)

cairosvg solo rasteriza con fuentes instaladas en el contenedor. En la práctica está la
familia **DejaVu**. Por eso el `font-family` SIEMPRE es:

```text
DejaVu Sans, Arial, sans-serif
```

Si pides "Inter" o "Amazon Ember" el PNG saldrá con fallback raro o métricas mal calculadas
(textos desbordados). Verifica fuentes disponibles:

```bash
fc-list | cut -d: -f2 | sort -u
```

### Caveats de XML / SVG

- SVG es XML estricto: escapa `<`, `>`, `&` en cualquier `<text>`.
  - `< 10 M` debe ir como `&lt; 10 M`. (Este fue un fallo real: rompe el parser.)
- Usa secuencias unicode `\uXXXX` en el código Python para acentos/flechas (→ `\u2192`,
  — `\u2014`, · `\u00b7`, ≥ `\u2265`, – `\u2013`) y deja que Python emita UTF-8.

---

## 4. Entrada: de mermaid a modelo de datos

Parsea el mermaid mentalmente a tres cosas:

1. **Nodos** con sus atributos. Ej. del label `MOVIMENTACAO\n2 860M filas` →
   `name=MOVIMENTACAO, rows="2 860 M", pii=False`.
2. **Aristas dirigidas** `A --> B` → `(A, B)`. Conserva la dirección del origen.
3. **Atributos derivables** que enriquecen el visual:
   - *Volumen* → tier de color (umbrales abajo).
   - *PII* → badge (si el label lo marca).
   - *Nivel topológico* → fila (ver layout).

No inventes semántica que no está (p. ej. cardinalidad 1:N con crow's-foot): el flowchart
solo da dirección. Etiqueta la leyenda como "dependencia / FK según el modelo".

Tiers de volumen usados (ajusta a tu dominio):

| Tier | Umbral filas | Color | Hex |
|---|---|---|---|
| masivo | ≥ 1 000 M | rojo | `#C0392B` |
| alto | 100–999 M | naranja | `#E8770F` |
| medio | 10–99 M | azul | `#2E6FE8` |
| bajo | < 10 M | verde | `#2E8B57` |

---

## 5. Sistema de diseño (tokens)

```text
Página         #FFFFFF
Banda fill     #FAFCFE   borde #DCE3EB  dash 6,4
Tarjeta fill   #FFFFFF   borde #C7D0DA
Flecha         #6B7A8A   width 1.6  marker triangular
Título         #16202C 18px bold    Subtítulo #5A6B7B 11.5px
Nombre tabla   #1A2A3A bold (tamaño dinámico, ver §6)
Tag/meta       #7B8794 9px
```

**Tarjeta** (210×86, rx8):
- Barra de acento vertical (5px, rx2.5) en color del tier, no toca esquinas.
- Ícono de tabla 20×16 (trazo en color del tier).
- Nombre (bold) + "N filas" (bold, color del tier) + "volumen <tier>" (gris).
- Badge PII opcional: chip 36×17 blanco, borde rojo, texto "PII".

**Iconografía**: glifos SVG simples (no PNG, no emoji). Cada categoría = trazo blanco o de
color sobre fondo de categoría. Mantén glifos de ~16–20px, stroke 1.6–2.

**Marcador de flecha** (definir una vez en `<defs>`):

```xml
<marker id="arr" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7"
        orient="auto-start-reverse">
  <path d="M2 1 L8 5 L2 9" fill="none" stroke="#6B7A8A" stroke-width="1.6"
        stroke-linecap="round" stroke-linejoin="round"/>
</marker>
```

---

## 6. Algoritmo de layout

### 6.1 Niveles topológicos (filas)

Asigna a cada nodo el nivel = longitud del camino más largo desde una raíz
(nodo sin aristas entrantes). Pseudocódigo:

```text
level[n] = 0 para todo n
repetir hasta estabilidad:
    para cada arista (a, b): level[b] = max(level[b], level[a] + 1)
```

Cada nivel es una fila horizontal (banda). En el ejemplo MMN salieron 3 niveles:
- N0 raíces: PESSOA, CARTAO, SESSAO, PROCESSAMENTOCLEARING_QR
- N1: PESSOA_FISICA, CARTAO_PESSOA, TRANSACAOUSOVALIDA, USOSQRVALIDOS, MOVIMENTO_SESSAO
- N2: MOVIMENTACAO, MOVIMENTO_SESSAO_PRODUTO

### 6.2 Orden dentro del nivel (reducir cruces)

Ordena por **baricentro**: posición media de los padres (y luego hijos) en el nivel
adyacente. Itera 1–2 pasadas. Para grafos pequeños se puede fijar a mano.

### 6.3 Grid de columnas

Define N columnas equiespaciadas (centros) y coloca cada tarjeta en un centro de columna.
Deja columnas vacías cuando un nivel tiene menos nodos (no las comprimas): el espacio en
blanco es legítimo y mantiene la rejilla legible.

```python
C  = [166, 418, 670, 922, 1174]      # 5 centros
T0, T1, T2 = 146, 296, 446           # tope de tarjeta por nivel (gap vertical ~64)
cW, cH = 210, 86
```

### 6.4 Tamaño de fuente dinámico del nombre

Nombres largos (`MOVIMENTO_SESSAO_PRODUTO`, 24 chars) desbordan a 11.5px. Escala:

```python
fs = max(9.3, min(11.5, 152 / (len(name) * 0.60)))
```

(0.60 ≈ ancho medio de carácter relativo al tamaño para DejaVu bold; ajusta si cambias fuente.)

---

## 7. Aristas: ruteo

- **Adyacentes** (nivel k → k+1): línea recta de *borde inferior del padre* a *borde
  superior del hijo*. Si varias aristas llegan al mismo hijo, **desplaza** los puntos de
  llegada ±12–16px para que no se solapen las puntas.
- **Largas** (k → k+2, saltan una fila): rutéalas **ortogonalmente** por un *canal* vertical
  entre columnas vacías, para no atravesar tarjetas. En el ejemplo, `CARTAO → MOVIMENTACAO`
  sale por el lado derecho de CARTAO, baja por `x=544` (canal entre col1 y col2, libre en
  todas las filas) y entra a MOVIMENTACAO por arriba:

```python
add(f'<path d="M{cr},{cmid} H544 V414 H{ex} V{movt}" fill="none" '
    f'stroke="#6B7A8A" stroke-width="1.6" marker-end="url(#arr)"/>')
```

- Unos pocos cruces entre aristas son aceptables y normales en ER; no sobre-optimices.
- Dibuja las aristas **antes** que las tarjetas para que las cajas queden por encima si una
  línea las roza.

---

## 8. Validación visual (obligatoria)

Renderiza y **abre el PNG** (no confíes en el SVG a ciegas). Checklist:

- [ ] El contenedor/canvas no recorta contenido. **Coherencia de alturas**: el `height` del
      rect contenedor y el `H` del canvas deben ser ≥ el `y` inferior del último elemento + margen.
      (Fallo típico: bajar `H` y olvidar el rect del contenedor → recorte.)
- [ ] Ningún texto desbordado de su tarjeta (revisa nombres largos).
- [ ] Ninguna flecha atraviesa una tarjeta; las largas van por canal.
- [ ] Puntas de flecha no encimadas cuando varias llegan al mismo nodo.
- [ ] Leyenda completa y alineada.
- [ ] Sin espacio vacío excesivo abajo (recorta `H` al contenido + margen 20–40px).

Comando de inspección: abrir el `.png` con la herramienta de visión del agente.

---

## 9. Entrega

```bash
cp /home/claude/model.png /mnt/user-data/outputs/<nombre>.png
cp /home/claude/model.svg /mnt/user-data/outputs/<nombre>.svg
```

Luego `present_files([png, svg])` con el **PNG primero** (vista) y el **SVG después** (editable).
Resumen breve. Sin postámbulo largo.

---

## 10. Script completo de referencia (ejemplo MMN)

Genera el diagrama de modelo de datos. Cópialo y cambia `nodes`, `meta`, `straight`,
`off` y el ruteo ortogonal para tu grafo.

```python
# -*- coding: utf-8 -*-
W, H = 1340, 690

PAGE="#FFFFFF"
BAND_FILL="#FAFCFE"; BAND_STROKE="#DCE3EB"
CARD_FILL="#FFFFFF"; CARD_STROKE="#C7D0DA"
ARROW="#6B7A8A"
TXT_TITLE="#16202C"; TXT_SUB="#5A6B7B"; TXT_NAME="#1A2A3A"; TXT_TAG="#7B8794"; TXT_LANE="#5E6E7E"
RED="#C0392B"; ORANGE="#E8770F"; BLUE="#2E6FE8"; GREEN="#2E8B57"; PII="#C0392B"
FONT="DejaVu Sans, Arial, sans-serif"

S=[]; add=S.append
cW, cH = 210, 86
C = [166, 418, 670, 922, 1174]
T0, T1, T2 = 146, 296, 446
BANDS = [("Nivel 0 \u00b7 entidades ra\u00edz (sin FK entrante)", 116),
         ("Nivel 1 \u00b7 derivadas / puente", 266),
         ("Nivel 2 \u00b7 hechos de alto volumen", 416)]

nodes = {'PES':(C[0],T0),'CAR':(C[1],T0),'PCL':(C[3],T0),'SES':(C[4],T0),
         'PEF':(C[0],T1),'CPE':(C[1],T1),'TVA':(C[2],T1),'USO':(C[3],T1),'MOS':(C[4],T1),
         'MOV':(C[2],T2),'MSP':(C[4],T2)}
meta = {'PES':("PESSOA","13.1 M",BLUE,True,"medio"),
        'PEF':("PESSOA_FISICA","13.1 M",BLUE,True,"medio"),
        'CAR':("CARTAO","16.4 M",BLUE,False,"medio"),
        'CPE':("CARTAO_PESSOA","16.0 M",BLUE,False,"medio"),
        'SES':("SESSAO","8.9 M",GREEN,False,"bajo"),
        'PCL':("PROCESSAMENTOCLEARING_QR","16.6 M",BLUE,False,"medio"),
        'USO':("USOSQRVALIDOS","8.1 M",GREEN,False,"bajo"),
        'MOS':("MOVIMENTO_SESSAO","997 M",ORANGE,False,"alto"),
        'MOV':("MOVIMENTACAO","2 860 M",RED,False,"masivo"),
        'TVA':("TRANSACAOUSOVALIDA","1 046 M",RED,False,"masivo"),
        'MSP':("MOVIMENTO_SESSAO_PRODUTO","1 354 M",RED,False,"masivo")}

def g_table(ix,iy,col):
    return (f'<rect x="{ix-10}" y="{iy-8}" width="20" height="16" rx="2" fill="none" stroke="{col}" stroke-width="1.6"/>'
            f'<line x1="{ix-10}" y1="{iy-2.5}" x2="{ix+10}" y2="{iy-2.5}" stroke="{col}" stroke-width="1.6"/>'
            f'<line x1="{ix}" y1="{iy-2.5}" x2="{ix}" y2="{iy+8}" stroke="{col}" stroke-width="1.1"/>'
            f'<line x1="{ix-10}" y1="{iy+2.7}" x2="{ix+10}" y2="{iy+2.7}" stroke="{col}" stroke-width="1"/>')

def card(key):
    cx,top=nodes[key]; name,rows,col,pii,tag=meta[key]; left=cx-cW//2
    o=[f'<rect x="{left}" y="{top}" width="{cW}" height="{cH}" rx="8" fill="{CARD_FILL}" stroke="{CARD_STROKE}" stroke-width="1"/>',
       f'<rect x="{left}" y="{top+10}" width="5" height="{cH-20}" rx="2.5" fill="{col}"/>',
       g_table(left+22,top+34,col)]
    fs=max(9.3,min(11.5,152/(len(name)*0.60)))
    o.append(f'<text x="{left+40}" y="{top+30}" font-family="{FONT}" font-size="{fs:.1f}" font-weight="bold" fill="{TXT_NAME}">{name}</text>')
    o.append(f'<text x="{left+40}" y="{top+50}" font-family="{FONT}" font-size="12" font-weight="bold" fill="{col}">{rows} filas</text>')
    o.append(f'<text x="{left+40}" y="{top+66}" font-family="{FONT}" font-size="9" fill="{TXT_TAG}">volumen {tag}</text>')
    if pii:
        bx=left+cW-46
        o.append(f'<rect x="{bx}" y="{top+9}" width="36" height="17" rx="8" fill="#FFFFFF" stroke="{PII}" stroke-width="1.2"/>')
        o.append(f'<text x="{bx+18}" y="{top+21}" font-family="{FONT}" font-size="9.5" font-weight="bold" fill="{PII}" text-anchor="middle">PII</text>')
    return "".join(o)

def arrow(x1,y1,x2,y2,w=1.6):
    return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{ARROW}" stroke-width="{w}" marker-end="url(#arr)"/>'
def bc(k): cx,t=nodes[k]; return (cx,t+cH)
def tc(k): cx,t=nodes[k]; return (cx,t)

add(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">')
add(f'<defs><marker id="arr" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
    f'<path d="M2 1 L8 5 L2 9" fill="none" stroke="{ARROW}" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></marker></defs>')
add(f'<rect x="0" y="0" width="{W}" height="{H}" fill="{PAGE}"/>')
add(f'<text x="28" y="44" font-family="{FONT}" font-size="18" font-weight="bold" fill="{TXT_TITLE}">Modelo de datos de origen \u2014 MMN</text>')
add(f'<text x="28" y="66" font-family="{FONT}" font-size="11.5" fill="{TXT_SUB}">11 tablas \u00b7 volumen de filas y dependencias (FK) del esquema \u00b7 PII se\u00f1alada \u00b7 niveles = profundidad topol\u00f3gica</text>')
for label,btop in BANDS:
    add(f'<rect x="40" y="{btop}" width="1260" height="126" rx="10" fill="{BAND_FILL}" stroke="{BAND_STROKE}" stroke-width="1" stroke-dasharray="6,4"/>')
    add(f'<text x="56" y="{btop+18}" font-family="{FONT}" font-size="10.5" font-weight="bold" fill="{TXT_LANE}" letter-spacing="0.3">{label}</text>')

off={'CPE':{'PES':-16,'CAR':0},'TVA':{'PES':-12,'CAR':12},'USO':{'PES':-16,'PCL':0},
     'PEF':{'PES':0},'MOS':{'SES':0},'MSP':{'MOS':0},'MOV':{'MOS':14}}
straight=[('PES','PEF'),('PES','CPE'),('PES','USO'),('PES','TVA'),('CAR','CPE'),
          ('CAR','TVA'),('SES','MOS'),('PCL','USO'),('MOS','MSP'),('MOS','MOV')]
for s,d in straight:
    x1,y1=bc(s); dx,dy=tc(d); add(arrow(x1,y1,dx+off.get(d,{}).get(s,0),dy))
carcx,cart=nodes['CAR']; movcx,movt=nodes['MOV']
add(f'<path d="M{carcx+cW//2},{cart+cH//2} H544 V414 H{movcx-14} V{movt}" fill="none" stroke="{ARROW}" stroke-width="1.6" marker-end="url(#arr)"/>')
for k in nodes: add(card(k))

ly=566
add(f'<rect x="40" y="{ly}" width="1260" height="96" rx="10" fill="{CARD_FILL}" stroke="{CARD_STROKE}" stroke-width="1"/>')
add(f'<text x="58" y="{ly+24}" font-family="{FONT}" font-size="11.5" font-weight="bold" fill="{TXT_LANE}">Leyenda</text>')
add(f'<text x="58" y="{ly+52}" font-family="{FONT}" font-size="10.5" fill="{TXT_LANE}">Volumen (n\u00ba filas):</text>')
tiers=[(RED,"\u2265 1 000 M \u00b7 masivo"),(ORANGE,"100\u2013999 M \u00b7 alto"),
       (BLUE,"10\u201399 M \u00b7 medio"),(GREEN,"&lt; 10 M \u00b7 bajo")]
x=180
for c,t in tiers:
    add(f'<rect x="{x}" y="{ly+43}" width="13" height="13" rx="3" fill="{c}"/>')
    add(f'<text x="{x+20}" y="{ly+53}" font-family="{FONT}" font-size="10.5" fill="{TXT_LANE}">{t}</text>')
    x+=26+len(t)*6.3
y2=ly+78
add(f'<rect x="58" y="{y2-12}" width="34" height="16" rx="8" fill="#FFFFFF" stroke="{PII}" stroke-width="1.2"/>')
add(f'<text x="75" y="{y2}" font-family="{FONT}" font-size="9.5" font-weight="bold" fill="{PII}" text-anchor="middle">PII</text>')
add(f'<text x="100" y="{y2}" font-family="{FONT}" font-size="10.5" fill="{TXT_LANE}">datos personales (enmascarar / tokenizar aguas abajo)</text>')
add(f'<line x1="470" y1="{y2-4}" x2="506" y2="{y2-4}" stroke="{ARROW}" stroke-width="1.6" marker-end="url(#arr)"/>')
add(f'<text x="516" y="{y2}" font-family="{FONT}" font-size="10.5" fill="{TXT_LANE}">dependencia / FK seg\u00fan el modelo (origen \u2192 derivado)</text>')
add('</svg>')

open("model.svg","w").write("\n".join(S))
import cairosvg
cairosvg.svg2png(url="model.svg", write_to="model.png", scale=2.0, background_color="#ffffff")
print("ok")
```

---

## 11. Cómo adaptarlo a OTRO diagrama

Cambia solo estos bloques:

1. **`nodes`** — clave corta → `(columna, fila)`. Calcula filas con §6.1 y columnas con §6.2.
2. **`meta`** — por nodo: `(nombre, métrica, color_categoría, badge?, tag)`.
3. **`straight`** y **`off`** — lista de aristas y desplazamientos de llegada.
4. **Ruteo ortogonal** — una línea `<path ... H.. V.. H.. V..>` por cada arista que salte fila.
5. **Paleta** — si NO es modelo de datos sino arquitectura de servicios, cambia tiers de
   volumen por **categorías AWS** (Storage `#56932E`, Analytics `#8C4FFF`, Compute `#ED7100`,
   Integración `#E7157B`, DB `#3B48CC`, open-source gris `#5A6B7B`) y usa glifos de servicio
   (cilindro=DB, cubeta=S3, λ=Lambda, etc.) en cajas con relleno de categoría y glifo blanco.
6. **Bandas/contenedores** — agrupa por VPC/zona/dominio según el caso; borde punteado =
   agrupador lógico, borde sólido = zona definida.

Mantén invariante: `font-family` DejaVu, escapado XML, validación visual del PNG, coherencia
de alturas canvas↔contenedor.

---

## 12. Errores comunes (todos vistos en la práctica)

| Síntoma | Causa | Fix |
|---|---|---|
| `ExpatError: not well-formed` | `<`/`&` sin escapar en `<text>` | `&lt;`, `&amp;` |
| Texto cortado / fuera de caja | fuente inexistente o nombre largo | DejaVu + fuente dinámica (§6.4) |
| Contenedor recortado | bajaste `H` pero no el `height` del rect | cuadrar ambos al contenido + margen |
| Flechas encimadas en un nodo | múltiples llegadas al mismo punto | desplazar puntos de llegada ±12–16 |
| Línea atraviesa una tarjeta | arista larga en recta | rutear ortogonal por canal libre |
| PNG borroso | escala 1x | `scale=2.0` en `svg2png` |
| `cairosvg` ausente | no instalado | `pip install cairosvg --break-system-packages` |

---

## 13. Prompt reutilizable para otro agente

> Tengo este mermaid: «PEGAR». Conviértelo en una **imagen** (PNG + SVG), no en mermaid,
> con estética de documentación AWS/ER limpia. Reglas: genera **SVG a mano** con Python y
> rasteriza con `cairosvg` (`pip install cairosvg --break-system-packages`). Usa
> `font-family="DejaVu Sans, Arial, sans-serif"` (es la única fiable en el contenedor) y
> escapa XML. Layout por **niveles topológicos** (fila por nivel), orden por baricentro,
> rejilla de columnas equiespaciadas con columnas vacías permitidas. Tarjetas con barra de
> acento por categoría, ícono, nombre, métrica y badge PII si aplica; bandas con borde
> punteado por nivel; flechas finas con marcador (las que salten fila, rutéalas ortogonales
> por un canal entre columnas vacías); leyenda con chips. **Abre el PNG y valida**: sin
> recortes (cuadra canvas y contenedores al contenido), sin texto desbordado, sin flechas
> sobre tarjetas. Entrega copiando a `/mnt/user-data/outputs/` y `present_files` con el PNG
> primero. No inventes cardinalidades que el flowchart no da.
