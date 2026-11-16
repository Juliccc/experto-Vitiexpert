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

## 4. Casos integrales (Pruebas E2E)

### Caso 1 — Diagnóstico y clima
> "En el lote norte 1 observo polvillo ceniza en las hojas. Hay 25 °C, 65 % de humedad y la etapa es floración. ¿Qué puede estar ocurriendo?"
* **Cruza:** Diagnóstico presuntivo (Julián) + Evaluación bioclimática (Alejo).
* **Resultado Esperado:** El sistema identifica Oídio y confirma que las condiciones climáticas (25°C y 65% HR) respaldan la hipótesis visual (`Confirmado_Clima_Propicio`).

### Caso 2 — Prescripción con control de carencia
> "Necesito una recomendación para el lote sur 2. Hay oídio, 75 % del área afectada, 26 °C, 70 % de humedad y faltan 10 días para cosecha."
* **Cruza:** Diagnóstico + Riesgo bioclimático + Bloqueo crisp normativo + Selección difusa (Patricio).
* **Resultado Esperado:** Diagnóstico de Oídio con clima propicio. El motor de prescripción bloquea automáticamente los fungicidas sintéticos (ej. Miclobutanil) por tener una carencia > 10 días (`Descartado_Por_LMR`). Calcula la viabilidad agronómica por centroide y selecciona una alternativa segura de corto plazo.

### Caso 3 — Evento inhibitorio y refutación
> "En el lote oeste 3 hay síntomas compatibles con peronóspora, pero hubo viento Zonda, 36 °C y 14 % de humedad."
* **Cruza:** Diagnóstico + Evento inhibitorio extremo.
* **Resultado Esperado:** Detecta síntomas de Peronóspora, pero la regla bioclimática intercepta el evento "Viento Zonda". Emite el dictamen `Refutado_Inhibicion_Zonda`, cancelando cualquier alerta severa y evitando una prescripción química innecesaria.

### Caso 4 — Consulta normativa directa
> "¿Puedo aplicar Miclobutanil en el lote norte 1 si faltan 10 días para cosecha?"
* **Cruza:** Consulta directa al Vademécum en Neo4j.
* **Resultado Esperado:** Devuelve los datos de carencia registrados en el grafo sin ejecutar el motor difuso, advirtiendo sobre la restricción de los 14 días.

### Caso 5 — Entrada inválida (Guardrails)
> "Quiero saber el pronóstico del tiempo para mañana."
* **Cruza:** Clasificación de intención en Fase 0 + Validación Python.
* **Resultado Esperado:** El prompt maestro asigna `FUERA_DE_DOMINIO`. El orquestador devuelve un error HTTP 400 controlado explicando los límites del sistema fitosanitario, sin ejecutar consultas inútiles en la base de datos.

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
