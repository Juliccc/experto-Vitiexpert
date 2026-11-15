# VITI-EXPERT — Integración PG3

## 1. Punto de entrada unificado

El asistente recibe una consulta única mediante:

- Interfaz web: `http://localhost:8000`
- API: `POST /consultar`
- Audio: `POST /transcribir`, seguido de `POST /consultar`

El usuario no debe elegir manualmente un submódulo. El prompt maestro clasifica la intención
y el orquestador ejecuta el flujo correspondiente.

## 2. Arquitectura

```text
Usuario / audio
      |
      v
Interfaz web
      |
      v
Prompt maestro + extracción estructurada
      |
      v
Validación determinística
      |
      v
Neo4j: conocimiento explícito
      |
      +--> Diagnóstico presuntivo
      +--> Riesgo bioclimático
      +--> Normativa crisp y carencia
      +--> Inferencia Mamdani
      |
      v
Trazabilidad PG3
      |
      v
Explicación grounded
```

Neo4j y los motores determinísticos son la fuente de verdad. El LLM no decide umbrales,
diagnósticos definitivos ni tratamientos por fuera de la evidencia recuperada.

## 3. Enrutamiento maestro

| Intención | Submódulos |
|---|---|
| `DIAGNOSTICO_LOTE` | Diagnóstico + riesgo bioclimático |
| `PRESCRIPCION` | Diagnóstico + riesgo + prescripción |
| `CONSULTA_CARENCIA` | Prescripción/normativa |
| `FUERA_DE_DOMINIO` | Ninguno; se rechaza |

Cada respuesta incluye `orquestacion_pg3`, donde se registra la intención, los módulos
ejecutados y las fuentes de verdad utilizadas.

## 4. Casos integrales

### Caso 1 — Diagnóstico y clima

```text
En el lote norte 1 observo polvillo ceniza en las hojas. Hay 25 °C,
65 % de humedad y la etapa es floración. ¿Qué puede estar ocurriendo?
```

Cruza diagnóstico presuntivo y evaluación bioclimática.

### Caso 2 — Prescripción con control de carencia

```text
Necesito una recomendación para el lote sur 2. Hay oídio, 75 % del área
afectada, 26 °C, 70 % de humedad y faltan 10 días para cosecha.
```

Cruza diagnóstico, riesgo, bloqueo crisp por carencia y selección difusa.

### Caso 3 — Evento inhibitorio

```text
En el lote oeste 3 hay síntomas compatibles con peronóspora, pero hubo
viento Zonda, 36 °C y 14 % de humedad.
```

Cruza diagnóstico, evento inhibitorio y explicación del alcance de la evidencia.

### Caso 4 — Consulta normativa

```text
¿Puedo aplicar Miclobutanil en el lote norte 1 si faltan 10 días para cosecha?
```

Ejecuta la consulta de carencia y devuelve el resultado del grafo.

### Caso 5 — Entrada inválida

```text
Quiero saber el pronóstico del tiempo para mañana.
```

Se clasifica fuera de dominio y no se ejecutan consultas expertas.

## 5. Trazabilidad

La respuesta contiene:

- datos extraídos y errores de validación;
- intención y submódulos ejecutados;
- consultas Cypher;
- reglas bioclimáticas;
- activaciones fuzzy;
- control de carencia;
- resultado final;
- explicación generada o fallback determinístico.

## 6. Ejecución

```powershell
docker compose up --build
```

Abrir:

```text
http://localhost:8000
```

Las pruebas locales se ejecutan con:

```powershell
python -m pytest -q
```
