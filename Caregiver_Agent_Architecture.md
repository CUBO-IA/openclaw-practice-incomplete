# Caregiver Agent (Agente Cuidador)

## 1. Propósito

Crear una aplicación local, modular y orientada a la privacidad que ayude a organizar los cuidados cotidianos de personas con enfermedades crónicas. Un **agente principal** coordina agentes especializados para citas, medicamentos, actividad física, registro/historial, comunicación con cuidadores humanos y supervisión.

El libro **SaludSV_Pro.xlsx** es la referencia funcional inicial. Contiene módulos equivalentes a: Inicio, Citas Médicas, Medicamentos, Ejercicios, Dieta, Historial e Instrucciones. La aplicación debe convertir esos registros en datos estructurados y procesos verificables; no depender de Excel como única base de datos en producción.

## 2. Principios de diseño

- **Local-first:** datos y lógica principal en el dispositivo del paciente o equipo autorizado. Internet solo para funciones explícitamente habilitadas, como mensajería externa o sincronización consentida.
- **Humano en el circuito:** decisiones clínicas, cambios de dosis, cambios importantes de ejercicio y respuestas a alertas críticas deben involucrar al paciente, profesional o cuidador autorizado.
- **No sustituye al personal sanitario:** ofrece organización, recordatorios y orientación segura; no diagnostica ni prescribe.
- **Trazabilidad:** registrar eventos, cambios, confirmaciones, fallos de entrega y quién realizó cada acción.
- **Privacidad por defecto:** recopilar lo mínimo necesario, cifrar datos en reposo y en tránsito, aplicar roles y permisos.
- **Resiliencia:** los recordatorios locales deben funcionar sin conexión cuando el sistema operativo lo permita. Las integraciones externas pueden fallar sin borrar ni perder registros.
- **Datos explícitos:** si falta información, pedirla o indicar “no registrado”; nunca inventar datos médicos.
- **Accesibilidad:** lenguaje sencillo, interfaz legible, controles grandes y flujos utilizables por adultos mayores o personas con limitaciones.

## 3. Arquitectura de alto nivel

```text
Paciente / Cuidador autorizado
            |
      Interfaz local
            |
      Agente principal
            |
  +---------+----------+-----------+-----------+-----------+
  |         |          |           |           |           |
Citas   Medicamentos  Actividad  Registro   Conexión   Control
                      física      e historial
            |
     Almacén local de datos
            |
 Motor de recordatorios / alarmas
            |
 Adaptadores de notificación (local, WhatsApp*, Telegram, Discord)
```

`*` WhatsApp es el canal externo preferido por defecto, pero requiere una integración oficial y configuración autorizada. No asumir que una cuenta personal permite automatización. Si no está disponible, usar Telegram, Discord o notificaciones locales según configuración. No enviar datos clínicos sensibles en mensajes externos por defecto; enviar alertas mínimas y un enlace o instrucción segura para consultar la aplicación.

### Componentes recomendados

- **Interfaz:** aplicación web local o escritorio; definir tecnología en una decisión de arquitectura separada.
- **Servicio local:** API interna y lógica de negocio.
- **Base de datos:** SQLite para una instalación individual; cifrado de archivos y copias de seguridad protegidas.
- **Planificador:** tareas persistentes con zona horaria local, reintentos y protección contra recordatorios duplicados.
- **Motor de agentes:** orquestador con herramientas de alcance limitado. La lógica determinista (horarios, stock, fechas, registro) debe resolverse con código normal, no con generación libre de un LLM.
- **Capa de integración:** adaptadores intercambiables para notificaciones, exportación e importación de Excel.
- **Auditoría:** registro append-only de eventos importantes, con control de acceso y política de retención.

## 4. Agente principal (Orchestrator / Main Agent)

### Misión
Coordinar el flujo de trabajo y delegar tareas a los agentes especializados. Mantiene el estado operativo general del paciente y presenta una vista unificada de pendientes y alertas.

### Responsabilidades
1. Leer el contexto mínimo necesario del paciente con autorización.
2. Enviar cada tarea al agente correcto.
3. Resolver prioridades según reglas deterministas: emergencia/síntoma potencialmente grave, dosis omitida de riesgo según plan clínico, cita próxima, stock bajo y recordatorios rutinarios.
4. Unificar resultados sin alterar registros fuente.
5. Detectar conflictos, datos faltantes o eventos duplicados.
6. Escalar a un humano cuando la situación exceda reglas seguras.
7. Mostrar la fuente, fecha y estado de cada dato importante.

### No debe
- Diagnosticar, prescribir, cambiar dosis o modificar tratamientos.
- inferir alergias, diagnósticos, horarios o identidad de profesionales.
- ocultar errores de agentes o afirmar que una notificación fue entregada sin confirmación técnica.
- reemplazar la aprobación humana requerida.

## 5. Agente de citas médicas

### Datos de entrada
Fecha, hora, profesional, especialidad, clínica/hospital, dirección, motivo, estado, costo opcional y notas. Estos campos corresponden al módulo “CITAS MÉDICAS” de SaludSV Pro.

### Funciones
- Crear, editar, cancelar y consultar citas con confirmación del usuario.
- Generar recordatorios locales:
  - **24 horas antes** de la cita.
  - **2 horas antes** de la cita.
- Incluir quién atiende, especialidad, lugar/dirección, fecha y hora.
- Evitar duplicados; actualizar o cancelar recordatorios cuando cambie la cita.
- Registrar confirmación, reprogramación, cancelación y resultado si el paciente lo informa.
- Detectar datos incompletos y solicitar aclaración.

### Reglas
- La zona horaria será la local del dispositivo, configurable.
- Si el equipo está apagado o el permiso de notificaciones está desactivado, informar que no se puede garantizar la alarma.
- No marcar una cita como atendida solo porque pasó la hora.
- Si el recordatorio falla, registrar el fallo y reintentar según política; no afirmar que fue recibido.

## 6. Agente de medicamentos

### Datos de entrada
Nombre, presentación, dosis prescrita, vía, frecuencia, horarios, instrucciones (por ejemplo, con alimentos), cantidad disponible, umbral de alerta, duración estimada del stock, condición crónica y prescriptor si se conoce. El libro incluye campos equivalentes en “MEDICAMENTOS”.

### Funciones
- Programar recordatorios de toma según el esquema confirmado.
- Permitir registrar con un clic: **Tomado**, **Omitido**, **Pospuesto** o **No confirmado**.
- Guardar fecha/hora prevista, acción, hora real, usuario y observaciones.
- Calcular días de stock con reglas verificables usando cantidad y pauta confirmadas.
- Alertar con anticipación para solicitar refill. La regla del proyecto es **10 días antes de la fecha estimada de agotamiento**; mostrar además alertas de urgencia cuando el stock esté bajo o agotado.
- Generar una solicitud/orden de refill como **borrador pendiente de aprobación**, no como orden médica o compra automática, salvo integración autorizada.
- Escalar al cuidador humano ante incumplimientos configurables (por ejemplo, toma no confirmada después del margen de gracia) y ante stock crítico.
- Ofrecer orientación segura cuando se omita una dosis: consultar las instrucciones oficiales del medicamento o contactar al farmacéutico/médico. No recomendar duplicar la dosis ni improvisar instrucciones específicas.
- Registrar síntomas anormales reportados y aplicar reglas de escalamiento conservadoras.

### Reglas clínicas y de seguridad
- El esquema de dosis debe provenir del paciente, cuidador o fuente clínica verificada. No deducirlo a partir del nombre del fármaco.
- No iniciar, suspender, sustituir ni cambiar medicamentos o dosis.
- No recomendar “tomar ahora” una dosis omitida sin una instrucción fiable específica del medicamento.
- Si el paciente reporta síntomas graves o potencialmente urgentes, mostrar instrucciones de buscar ayuda de emergencia local y avisar al cuidador autorizado según el protocolo configurado. No retrasar la atención por completar preguntas.
- Diferenciar **no confirmado** de **no tomado**.
- La cantidad de stock debe actualizarse por una toma registrada, una reposición o una corrección explícita; conservar el valor anterior en auditoría.
- Los cálculos deben contemplar frecuencia, unidades por toma, días de tratamiento y dosis variables. Si la pauta no permite un cálculo fiable, indicar “stock no calculable” y pedir revisión.

## 7. Agente de actividad física

### Datos de entrada
Nombre de rutina, fecha de inicio, ejercicios, grupos musculares, series, repeticiones/tiempo, peso opcional, descanso, días, técnica/notas, cumplimiento y síntomas reportados. El módulo “EJERCICIOS” contiene estructura similar y actualmente sugiere revisar la rutina aproximadamente cada seis semanas.

### Funciones
- Recordar el ejercicio según calendario aprobado.
- Registrar completado, parcial, omitido o pospuesto; permitir registrar duración y comentarios.
- Registrar síntomas durante o después de la actividad (por ejemplo, dolor, mareo, falta de aire inusual, palpitaciones o debilidad).
- Proponer revisión de rutina cada **8 semanas** como objetivo de producto configurable; el libro de referencia muestra un ciclo de **6 semanas**, por lo que la importación debe conservar el valor existente y permitir elegir el intervalo sin sobrescribirlo silenciosamente.
- Proponer ajustes solo como sugerencias para revisión del paciente, entrenador o profesional sanitario; no cambiar automáticamente un plan clínico.

### Reglas
- Respetar restricciones y recomendaciones ya documentadas por profesionales.
- No prescribir ejercicio de rehabilitación ni recomendar superar dolor o síntomas.
- Ante síntomas graves o potencialmente urgentes, detener la actividad y recomendar atención urgente conforme al protocolo de seguridad.
- La ausencia de registro no equivale a incumplimiento confirmado.
- No interpretar datos de wearables como diagnóstico.

## 8. Agente de registro e historial

### Misión
Mantener un historial cronológico, consistente y auditable de la información y de las acciones.

### Funciones
- Registrar cada cita, medicamento, pauta, ejercicio, síntoma, toma, cumplimiento, alerta, contacto y cambio.
- Clasificar los registros en módulos equivalentes a SaludSV Pro: citas, medicamentos, ejercicios, dieta (si se habilita), historial y panel principal.
- Guardar quién hizo el cambio, cuándo, valor anterior, valor nuevo, motivo opcional y origen (usuario/agente/importación).
- Mantener eventos originales; corregir mediante un nuevo evento o versión, no borrar silenciosamente.
- Ofrecer búsqueda, filtros y exportación autorizada.
- Importar Excel con vista previa, validación, mapeo de columnas y reporte de errores.
- Detectar posibles duplicados, pero pedir confirmación antes de fusionar.

### Reglas
- No inventar datos ausentes ni convertir notas libres en hechos confirmados sin marcar que son reportados.
- Separar datos clínicos, preferencias, inferencias y recomendaciones.
- Aplicar control de acceso, copias de seguridad y política de retención.
- No incluir datos sensibles en logs técnicos innecesarios.

## 9. Agente de conexión con cuidador humano

### Misión
Facilitar la comunicación de alertas y resúmenes al cuidador autorizado, con consentimiento explícito.

### Canales
1. **WhatsApp** como opción preferida cuando exista integración oficial y configuración válida.
2. Telegram.
3. Discord.
4. Notificación local como alternativa de base.

### Funciones
- Configurar contacto, canal, permisos, horarios de silencio y categorías de alertas.
- Enviar alertas sobre toma no confirmada/incumplimiento, síntomas anormales, stock crítico, cambios importantes y citas próximas.
- Enviar resúmenes de cumplimiento según una frecuencia configurable.
- Registrar estado de envío: pendiente, enviado, entregado si el proveedor lo confirma, fallido.
- Reintentar con límites y ofrecer alternativa configurada ante fallos.
- Permitir al cuidador confirmar recepción y registrar seguimiento, cuando la integración lo permita.

### Reglas
- Obtener consentimiento del paciente o representante legal autorizado.
- Verificar la identidad y autorización del destinatario.
- Compartir el mínimo necesario; no mandar historial clínico completo ni datos sensibles por defecto.
- No afirmar que el cuidador fue avisado si el proveedor no confirma el envío.
- Si todos los canales fallan, crear una alerta visible local y registrar el fallo.
- Los mensajes no sustituyen una llamada a emergencias ni garantizan supervisión humana continua.

## 10. Agente de control y supervisión

### Misión
Comprobar que los agentes, tareas y registros funcionen conforme a sus contratos.

### Verificaciones
- Agentes activos y herramientas disponibles.
- Recordatorios programados, vencidos, duplicados o fallidos.
- Integridad de fechas, horarios, zonas horarias y referencias.
- Coherencia entre tomas registradas y stock, sin asumir que cada registro representa consumo físico confirmado.
- Entrega y reintentos de mensajes.
- Eventos sin clasificar, registros huérfanos y conflictos de actualización.
- Cumplimiento de permisos, consentimiento, auditoría y política de datos.
- Calidad de respuestas de LLM: afirmaciones sin fuente, recomendaciones clínicas no autorizadas o datos inventados.

### Respuesta ante fallos
- Registrar el incidente con código, hora y severidad.
- Reintentar solo operaciones idempotentes y con límite.
- Alertar al usuario o administrador humano cuando el fallo afecte una función de seguridad.
- No modificar datos clínicos para “arreglar” inconsistencias sin autorización.
- Disponer de modo degradado: calendario y registros locales deben seguir disponibles aunque falle un LLM o canal externo.

## 11. Modelo de datos inicial

Entidades mínimas recomendadas:

- `Patient`: identificador local, datos básicos mínimos, zona horaria, preferencias y consentimientos.
- `Condition`: condición reportada/verificada, fuente y fecha.
- `Appointment`: fecha/hora, profesional, especialidad, centro, dirección, motivo, estado.
- `Medication`: nombre, presentación, pauta prescrita, instrucciones, prescriptor/fuente.
- `MedicationInventory`: cantidad, unidad, fecha de actualización y cálculo estimado.
- `MedicationEvent`: dosis prevista, estado, hora, actor, observaciones.
- `ExerciseRoutine` y `ExerciseItem`: rutina, inicio, intervalo de revisión y ejercicios.
- `ExerciseEvent`: actividad prevista, estado, duración y síntomas.
- `SymptomReport`: síntoma, hora, contexto, severidad reportada y fuente; no equivale a diagnóstico.
- `Reminder`: tipo, entidad asociada, fecha programada, estado, resultado y clave idempotente.
- `CaregiverContact`: canal, destinatario protegido, permisos y consentimiento.
- `NotificationEvent`: mensaje mínimo, canal, estado técnico y marcas de tiempo.
- `AuditEvent`: actor, acción, entidad, valores anterior/nuevo cuando corresponda y motivo.
- `AgentRun` / `Incident`: tarea, agente, estado, duración, errores y versión de reglas.

## 12. Reglas de recordatorios y alertas

| Evento | Regla inicial | Acción |
|---|---|---|
| Cita médica | 24 h antes y 2 h antes | Alarma local; registrar resultado |
| Medicamento | Según pauta confirmada | Recordatorio y botón de registro |
| Toma no confirmada | Tras margen de gracia configurable | Distinguir no confirmada de omitida; escalar según plan |
| Refill | 10 días antes del agotamiento estimado | Aviso y borrador de solicitud |
| Stock crítico/agostado | Umbral configurado | Alerta prioritaria al paciente/cuidador |
| Actividad física | Según plan aprobado | Recordatorio y registro |
| Revisión de rutina | 8 semanas por defecto, configurable | Proponer revisión; respetar datos importados de 6 semanas |
| Síntoma anormal | Según reglas de severidad conservadoras | Orientación segura y escalamiento humano |
| Error de agente/canal | Inmediato según severidad | Auditoría, reintento limitado y alerta |

## 13. Seguridad, privacidad y cumplimiento

- Autenticación local y roles separados: paciente, cuidador, administrador técnico y profesional si se habilita.
- Cifrado de base de datos/respaldos cuando sea viable; secretos de integración fuera del código fuente.
- Consentimiento revocable para cada cuidador y canal externo.
- Minimización de datos; no enviar datos médicos a un proveedor de LLM externo sin evaluación, consentimiento y configuración explícita.
- Control de acceso por necesidad de conocer.
- Registro de auditoría protegido contra modificaciones ordinarias.
- Copias de seguridad cifradas y proceso probado de restauración.
- No almacenar tokens, contraseñas ni secretos en Markdown, logs o repositorio.
- Definir retención, exportación y eliminación segura de datos.
- Evaluar la legislación salvadoreña aplicable, las obligaciones sanitarias y las condiciones de cada proveedor antes de usar datos reales. Este documento no constituye asesoría legal.

## 14. Uso de LLM y prevención de alucinaciones

- Usar código determinista para cálculos, calendarios, inventario, permisos, persistencia y reglas de escalamiento.
- Usar LLM solo para tareas acotadas: resumir registros existentes, clasificar texto reportado con incertidumbre explícita o redactar mensajes aprobados.
- Entregar al modelo solo el contexto mínimo y estructurado.
- Restringir las salidas a esquemas tipados/JSON validado cuando corresponda.
- Exigir fuente/registro de origen para cada dato médico factual.
- Si la información es insuficiente, responder “No hay información suficiente en el registro”.
- Validar la salida antes de ejecutar cualquier herramienta; nunca permitir que texto del modelo ejecute SQL arbitrario o comandos del sistema.
- No permitir que agentes se cambien entre sí permisos, reglas de seguridad o herramientas.

## 15. Flujo de trabajo de extremo a extremo

1. El usuario importa o registra datos y revisa la vista previa.
2. La aplicación valida, identifica datos incompletos y solicita confirmación.
3. El agente de registro guarda las entidades y los eventos de auditoría.
4. El agente principal solicita a los agentes pertinentes que calculen recordatorios y alertas.
5. El planificador guarda tareas persistentes con claves idempotentes.
6. Cuando llega una hora, el sistema emite la notificación local y registra el resultado.
7. El usuario confirma una toma, cita o ejercicio; se guarda un evento nuevo.
8. El agente de control valida consistencia y fallos.
9. Si se activa una regla de escalamiento, el agente de conexión intenta contactar al cuidador autorizado.
10. El historial muestra qué ocurrió, cuándo, quién lo registró y el estado real de cada acción.

## 16. Fases de desarrollo sugeridas

### Fase 1 — Base fiable
- Esquema de datos, almacenamiento local, importador Excel, auditoría y autenticación.
- CRUD de citas, medicamentos y rutinas.
- Pruebas de fechas, zonas horarias, inventario y duplicados.

### Fase 2 — Recordatorios locales
- Motor persistente de recordatorios.
- Citas 24 h/2 h antes y tomas según pauta.
- Registro con un clic y estados explícitos.

### Fase 3 — Alertas y supervisión
- Stock/refill, incumplimiento, síntomas y agente de control.
- Reglas de severidad revisadas por profesionales apropiados.

### Fase 4 — Cuidador humano
- Consentimiento, adaptadores de mensajería, confirmaciones, reintentos y auditoría.
- WhatsApp solo mediante una integración oficial válida.

### Fase 5 — Asistencia con LLM
- Resúmenes y clasificación limitada, con evaluaciones, pruebas adversariales y control de costos.
- Nunca bloquear las funciones principales si el LLM no está disponible.

### Fase 6 — Validación y despliegue
- Pruebas de seguridad, accesibilidad, recuperación de respaldos, errores de red y horarios de verano/zona horaria si aplica.
- Prueba piloto con datos ficticios; no usar datos reales hasta completar revisión de privacidad y seguridad.

## 17. Criterios mínimos de aceptación

- Los recordatorios de citas se generan exactamente una vez por cita y por anticipación configurada.
- Editar/cancelar una cita actualiza sus recordatorios anteriores.
- Las tomas pueden registrarse en un clic y el sistema distingue tomado, omitido y no confirmado.
- El cálculo de stock muestra los datos y supuestos utilizados; ante datos insuficientes no inventa un resultado.
- Los avisos de refill se activan según la regla de 10 días y admiten corrección manual auditada.
- La revisión de rutina usa un intervalo configurable y no altera silenciosamente el ciclo importado.
- Todo cambio relevante genera un evento de historial.
- Las notificaciones muestran estado técnico real y registran fallos.
- Un LLM no puede cambiar dosis, borrar registros, modificar permisos ni enviar datos externos sin validación.
- La aplicación sigue permitiendo consultar y registrar datos básicos sin internet ni servicio LLM.
- Las pruebas cubren datos vacíos, duplicados, cambios de hora, reinicio del equipo, fallos de canal y restauración de respaldo.

## 18. Decisiones pendientes antes de programar

1. Sistema operativo objetivo y tipo de aplicación (web local o escritorio).
2. Si se usará SQLite y qué mecanismo de cifrado.
3. Qué sistema operativo soportará alarmas persistentes cuando la aplicación esté cerrada.
4. Integración oficial concreta de WhatsApp y costos/limitaciones del proveedor.
5. Quién puede ver datos, aprobar refill y recibir cada clase de alerta.
6. Definición clínica revisada de síntomas de alarma, márgenes de gracia y protocolos de escalamiento.
7. Intervalo de cambio de rutina: el objetivo solicitado es 8 semanas, mientras que el Excel de referencia indica 6 semanas.
8. Cómo se protegerán los datos durante copias de seguridad, exportaciones y uso opcional de LLM.

---
**Estado:** especificación inicial de producto y arquitectura. Los detalles clínicos, de privacidad e integración deben validarse antes del uso con pacientes reales.
