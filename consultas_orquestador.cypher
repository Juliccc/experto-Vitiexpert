// ============================================================
// Consultas Cypher del orquestador VITI-EXPERT
// ============================================================

// ============================================================
// Módulo 1 — Diagnóstico (Julián)
// ============================================================

// C1_DIAGNOSTICO_LOTE
MATCH (l:Lote_Vinedo)
MATCH (s:Sintoma_Visual)-[:GENERA_HIPOTESIS]->(d:Diagnostico_Presuntivo)-[:IDENTIFICA_CANDIDATO]->(p:Patologia_Fungica)
MATCH (e:Evidencia_Climatica)-[:CONFIRMA_O_REFUTA]->(d)
WHERE substring(l.id_lote, size(l.id_lote)-2) = substring(d.id_diag, 5)
  AND substring(s.id_sintoma, 8) = substring(e.id_clima, 6)
  AND l.id_lote = $lote_id
RETURN l.id_lote AS lote, l.etapa_fenologica AS etapa, l.porcentaje_area_afectada AS area_afectada_pct,
       s.ubicacion AS ubicacion, s.textura AS textura, s.distribucion AS distribucion,
       p.nombre AS patologia, p.etapas_susceptibles AS etapas_susceptibles,
       e.temperatura_media AS temperatura_c, e.humedad_relativa AS humedad_pct,
       e.evento_inhibitorio_reciente AS evento_inhibitorio,
       CASE
         WHEN e.evento_inhibitorio_reciente = true OR e.humedad_relativa < 20.0 THEN "Refutado_Inhibicion_Zonda"
         WHEN l.etapa_fenologica IN p.etapas_susceptibles AND e.temperatura_media >= 10.0 THEN "Confirmado_Clima_Propicio"
         ELSE "Atenuado_Condicion_Suboptima"
       END AS dictamen_bioclimatico
ORDER BY l.id_lote;

// C2_LOTES_POR_PATOLOGIA
MATCH (l:Lote_Vinedo)
MATCH (s:Sintoma_Visual)-[:GENERA_HIPOTESIS]->(d:Diagnostico_Presuntivo)-[:IDENTIFICA_CANDIDATO]->(p:Patologia_Fungica)
MATCH (e:Evidencia_Climatica)-[:CONFIRMA_O_REFUTA]->(d)
WHERE substring(l.id_lote, size(l.id_lote)-2) = substring(d.id_diag, 5)
  AND substring(s.id_sintoma, 8) = substring(e.id_clima, 6)
  AND p.nombre = $patologia
RETURN l.id_lote AS lote, l.etapa_fenologica AS etapa, l.porcentaje_area_afectada AS area_afectada_pct,
       s.ubicacion AS ubicacion, s.textura AS textura, s.distribucion AS distribucion,
       p.nombre AS patologia, p.etapas_susceptibles AS etapas_susceptibles,
       e.temperatura_media AS temperatura_c, e.humedad_relativa AS humedad_pct,
       e.evento_inhibitorio_reciente AS evento_inhibitorio,
       CASE
         WHEN e.evento_inhibitorio_reciente = true OR e.humedad_relativa < 20.0 THEN "Refutado_Inhibicion_Zonda"
         WHEN l.etapa_fenologica IN p.etapas_susceptibles AND e.temperatura_media >= 10.0 THEN "Confirmado_Clima_Propicio"
         ELSE "Atenuado_Condicion_Suboptima"
       END AS dictamen_bioclimatico
ORDER BY l.id_lote;

// C3_INFO_PATOLOGIA
MATCH (p:Patologia_Fungica {nombre: $patologia})
RETURN p.nombre AS patologia, p.etapas_susceptibles AS etapas_susceptibles,
       p.requiere_agua_libre AS requiere_agua_libre;

// ============================================================
// Módulo 2 — Riesgo bioclimático (Alejo)
// ============================================================

// CYPHER_CONDICION
MATCH (p:Patologia_Fungica {nombre: $patologia})-[:REQUIERE_CONDICION]->(c:CondicionClimatica)
OPTIONAL MATCH (p)-[:POSIBLE_EN]->(e:EtapaFenologica)
RETURN p.nombre AS patologia, p.requiere_agua_libre AS requiere_agua_libre,
       c.id_condicion AS id_condicion,
       c.temp_min AS temp_min, c.temp_max AS temp_max,
       c.temp_optima_min AS temp_optima_min, c.temp_optima_max AS temp_optima_max,
       c.humedad_min AS humedad_min, c.humedad_max AS humedad_max,
       c.humedad_optima_min AS humedad_optima_min, c.humedad_optima_max AS humedad_optima_max,
       c.horas_mojado_min AS horas_mojado_min, c.fuente AS fuente,
       collect(DISTINCT e.nombre) AS etapas_susceptibles;

// CYPHER_EVENTOS_INHIBITORIOS
MATCH (e:EventoInhibitorio)-[:INHIBE]->(:Patologia_Fungica {nombre: $patologia})
RETURN e.nombre AS evento, e.tipo AS tipo, e.temp_disparo_min AS temp_disparo_min,
       e.humedad_max_limite AS humedad_max_limite, e.descripcion AS descripcion
ORDER BY evento;

// CYPHER_REGLAS_BIOCLIMATICAS
MATCH (r:ReglaBioclimatica)-[:APLICA_A]->(:Patologia_Fungica {nombre: $patologia})
RETURN r.codigo AS codigo, r.nombre AS nombre, r.estrategia AS estrategia,
       r.prioridad AS prioridad, r.descripcion AS descripcion
ORDER BY prioridad, codigo;

// ============================================================
// Módulo 3 — Prescripción Mamdani (Patricio)
// ============================================================

// CYPHER_Q1_CRISP
MATCH (l:Lote_Vinedo {id_lote: $id_lote})-[:EVALUA_INOCUIDAD]->(t:Tratamiento)-[:COMBATE]->(p:Patologia_Fungica)
MATCH (t)-[:UTILIZA_QUIMICO]->(pa:Principio_Activo)
MATCH (s:Sintoma_Visual)-[:GENERA_HIPOTESIS]->(d:Diagnostico_Presuntivo)-[:IDENTIFICA_CANDIDATO]->(p)
MATCH (e:Evidencia_Climatica)-[:CONFIRMA_O_REFUTA]->(d)
WHERE substring(s.id_sintoma, 8) = substring(e.id_clima, 6)
  AND substring(l.id_lote, size(l.id_lote)-2) = substring(d.id_diag, 5)
  AND ($patologia IS NULL OR p.nombre = $patologia)
  AND ($etapa_fenologica IS NULL OR l.etapa_fenologica = $etapa_fenologica)
SET l.dias_para_cosecha = COALESCE($dias_para_cosecha, l.dias_para_cosecha),
    l.porcentaje_area_afectada = COALESCE($porcentaje_area_afectada, l.porcentaje_area_afectada)
SET d.factor_certeza_ambiental = CASE
    WHEN e.evento_inhibitorio_reciente = true OR e.humedad_relativa < 20.0 THEN "Refutado_Inhibicion_Zonda"
    WHEN l.etapa_fenologica IN p.etapas_susceptibles AND e.temperatura_media >= 10.0 THEN "Confirmado_Clima_Propicio"
    ELSE "Atenuado_Condicion_Suboptima"
END
SET t.viabilidad_agronomica = 0.0,
    t.estado_evaluacion = CASE
        WHEN d.factor_certeza_ambiental = "Refutado_Inhibicion_Zonda" THEN "Cancelado_Falso_Positivo"
        WHEN pa.dias_carencia > l.dias_para_cosecha THEN "Descartado_Por_LMR"
        ELSE "Admisible"
    END
RETURN l.id_lote AS Lote, t.id_trat AS Tratamiento, t.estado_evaluacion AS Estado_Crisp;

// CYPHER_Q2_FUZZ
MATCH (l:Lote_Vinedo {id_lote: $id_lote})
WHERE EXISTS { MATCH (l)-[:EVALUA_INOCUIDAD]->(:Tratamiento {estado_evaluacion: "Admisible"}) }
UNWIND [
    {var: "Severidad_de_la_Infeccion", valor: l.porcentaje_area_afectada},
    {var: "Proximidad_a_Cosecha", valor: toFloat(l.dias_para_cosecha)}
] AS entrada
MATCH (v:VariableDifusa {nombreVariable: entrada.var})-[:TIENE_ETIQUETA]->(c:ConjuntoDifuso)-[:MODELADO_POR]->(f:FuncionPertenencia)
WITH l, v, c, f, entrada.valor AS x,
     exp(-0.5 * ((entrada.valor - f.centro_c) / f.dispersion_sigma) ^ 2) AS mu_calculado
MERGE (ls:LecturaSensor {id_lectura: l.id_lote + "_" + v.nombreVariable})
SET ls.id_lote = l.id_lote, ls.nombreVariable = v.nombreVariable, ls.valorCrisp = x
MERGE (ls)-[:ASOCIADO_A_VARIABLE]->(v)
MERGE (ls)-[ap:ACTIVACION_PARCIAL]->(c)
SET ap.mu = round(mu_calculado, 4)
RETURN count(ap) AS total_fuzzificados;

// CYPHER_Q3_REGLAS
MATCH (l:Lote_Vinedo {id_lote: $id_lote})
WHERE EXISTS { MATCH (l)-[:EVALUA_INOCUIDAD]->(:Tratamiento {estado_evaluacion: "Admisible"}) }
MATCH (r:ReglaDifusa)-[:DETERMINA_CONSECUENTE]->(c_out:ConjuntoDifuso)
MATCH (r)-[:EVALUA_ANTECEDENTE]->(c_ant1:ConjuntoDifuso {variable: "Proximidad_a_Cosecha"})
MATCH (r)-[:EVALUA_ANTECEDENTE]->(c_ant2:ConjuntoDifuso {variable: "Severidad_de_la_Infeccion"})
MATCH (ls1:LecturaSensor {id_lote: l.id_lote, nombreVariable: "Proximidad_a_Cosecha"})-[ap1:ACTIVACION_PARCIAL]->(c_ant1)
MATCH (ls2:LecturaSensor {id_lote: l.id_lote, nombreVariable: "Severidad_de_la_Infeccion"})-[ap2:ACTIVACION_PARCIAL]->(c_ant2)
WITH l, r, c_out,
     CASE
         WHEN r.operador = "MIN" THEN CASE WHEN ap1.mu < ap2.mu THEN ap1.mu ELSE ap2.mu END
         WHEN r.operador = "MAX" THEN CASE WHEN ap1.mu > ap2.mu THEN ap1.mu ELSE ap2.mu END
     END AS fuerza_disparo
MERGE (l)-[act:ACTIVA_CONSECUENTE {regla: r.codigoRegla}]->(c_out)
SET act.fuerza_activacion = round(fuerza_disparo, 4)
RETURN c_out.nombreEtiqueta AS etiqueta, max(act.fuerza_activacion) AS fuerza_maxima;

// CYPHER_Q4_TRAZABILIDAD
MATCH (s:Sintoma_Visual)-[:GENERA_HIPOTESIS]->(d:Diagnostico_Presuntivo)-[:IDENTIFICA_CANDIDATO]->(p:Patologia_Fungica)
MATCH (e:Evidencia_Climatica)-[:CONFIRMA_O_REFUTA]->(d)
MATCH (l:Lote_Vinedo {id_lote: $id_lote})-[:EVALUA_INOCUIDAD]->(t:Tratamiento)-[:COMBATE]->(p)
MATCH (t)-[:UTILIZA_QUIMICO]->(pa:Principio_Activo)
WHERE substring(s.id_sintoma, 8) = substring(e.id_clima, 6)
  AND substring(l.id_lote, size(l.id_lote)-2) = substring(d.id_diag, 5)
OPTIONAL MATCH (l)-[act:ACTIVA_CONSECUENTE]->(c_out:ConjuntoDifuso)
WITH l, p, d, e, t, pa,
     collect(DISTINCT {regla: act.regla, consecuente: c_out.nombreEtiqueta, alpha: act.fuerza_activacion}) AS reglas_difusas
RETURN l.id_lote AS Lote,
       l.etapa_fenologica AS Etapa_Fenologica,
       l.dias_para_cosecha AS Dias_Para_Cosecha,
       l.porcentaje_area_afectada AS Severidad_Porcentaje,
       p.nombre AS Patologia_Candidata,
       d.factor_certeza_ambiental AS Validacion_Bioclimatica,
       e.severidad_estimada AS Severidad_Campo,
       t.id_trat AS Tratamiento,
       pa.nombre_quimico AS Principio_Activo,
       (pa.nombre_quimico = $principio_activo) AS Quimico_Consultado_Por_Usuario,
       pa.espectro AS Espectro_Quimico,
       pa.dias_carencia AS Carencia_Registrada_Grafo,
       toString(pa.dias_carencia) + "d carencia registrada vs " + toString(l.dias_para_cosecha) + "d cosecha" AS Control_LMR,
       t.viabilidad_agronomica AS Viabilidad_Difusa_Porc,
       t.estado_evaluacion AS Conclusion_Final,
       reglas_difusas AS Reglas_Difusas_Activadas
ORDER BY t.id_trat;