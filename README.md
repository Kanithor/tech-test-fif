# Prueba técnica Platform Engineer FIF

## Parte 1

### Arquitectura y Uso

.csv -> Python -> GCP (Pub/Sub -> Cloud Run -> BigQuery -> Looker Studio)

1. Disponibilizar fuente de datos .csv (en nuestro caso ventas.csv)
2. Ejecutar publisher.py (push de msgs a tópico)
3. Tópico Pub/Sub recibe uno a uno registro de ventas de {mes anno} para un cierto producto y región.
4. Suscripción Pub/Sub conectada a nuestro CloudRun, que manipula y convierte la data para exportarla a BigQUery.
5. Desde Looker Studio ya es posible obtener información con ingesta desde BigQuery dataset "ventas_ds".

### Consideraciones
#### Python App
Como fue solicitado, el patrón de diseño de nuestro microservicio es el siguiente:
domain -> orchestation app -> inputs apps -> output app
- Dominio (domain): ports.py actúa como nuestra puerta de entrada al microservicio, solo invoca funciones y no posee dependencias.
- App orquestadora: procesar_venta_use_case.py no conoce de lógica ni dependencias, administra dónde enviar la data recibida.
- Inputs apps: en nuestro caso pubsub_message_decoder.py y flask_app.py, la primera conteniendo lógica de infrastructura y la segunda como el adaptador http.
- Output app: big_query_venta_repository.py ya con la data completamente adaptada es quien envía la info a BigQuery.

### Git
- CI/CD llevado a cabo en Github Actions, donde se hace build y push automático de cada nueva imagen Docker al Google Artifact Registry.

### GCP / Terraform
- Terraform utilizado para declarar infraestructura de nuestros Pub/Sub (tópico y sub), app CloudRUn y cuentas de servicio, con roles atomizados, a utilizar por estos recursos.

### Looker Studio
*Un detalle es que la prueba solicita ventas totales por departamento, como el dato no existe en ventas.csv, se utilizó la región para graficar data.

## Parte 2
Respuestas a las preguntas solicitadas:
1. Respondiendo literalmente, el pod se puede escalar en recursos computacionales (verticalmente) mediante la declaración de un Vertical Pod Autoscaler, que bajo cierta demanda (uso) este puede incrementar tales recursos. Ahora tomando atribuciones y saliendo de "escalar un pod", yo iría por una estrategia de "escalado de workload", ya que personalmente prefiero HPA (horizontal pod autoscaler) que en vez de aumentar "músculo" (cpu y ram), aumentamos réplicas (pods) dentro del workload. Ambas estrategias consideran un scale down cuando la demanda del servicio baja, considerando que se setean límites inferiores y superiores de recursos. A tomar en cuenta: capacidad del node pool, que este sea capaz de suministrar recursos para el workload en sus límites superiores.

2. Precisamente está implementado de esta forma, restringido sólo para que Pub/Sub pueda invocar a Cloudrun mediante la SA "sa-ventas-pubsub-invoker". Fuera de IAM, existe una alternativa a nivel VPC con perimeters.

3. La respuesta a este tipo de preguntas siempre es: depende. Para mí el factor más importante es el objetivo/necesidad del servicio/app. Me inclinaría a serverless si la demanda es esporádica y se requiere mínima "mantención", como por ejemplo un cronjob que a cierta hora del día haga una cierta ingesta/expulsión de datos o la parte 1 de esta prueba es un excelente ejemplo también. Para máquinas virtuales u orquestación de contenedores es cuando tenemos tráfico medianamente constante y/o predecible, buscamos un alto nivel de uptime y requerimos un sistema stateful. Un ejemplo podría ser un ERP o una página de ventas online.

4. El primer lugar donde recurrir es la herramienta de monitoreo/observabilidad, contar con dashboards de disponibilidad de nuestros recursos es indispensable, tanto del uso computacional/redes/almacenamiento de los servicios como de sus respectivos logs. Si el problema es la infraestructura entonces dependerá del problema su solución, algunos ejemplos pueden ser: recursos a tope de el/los servicio/s? aumentar replicas, nos quedamos sin ips? añadir subnet secundaria o reducir cantidad de pods de otros workloads que estén con baja demanda, base de datos a tope? eliminar data antigua y/o temporal, y así sucesivamente. En el caso que sea de comportamiento de servicios, podemos identificar mediante gráficos si algún servicio (api rest) se dispara en errores http 500s y 400s y de esa forma direccionar la problemática al equipo responsable de ese/esos servicio/s (en caso de aplicar). Fuera de lo "técnico", las preguntas que le haría al cliente serían si la interacción con el sistema lo hizo igual que siempre o no, le pediría también que replique el caso de uso y ver si hay algo que llame la atención (dirección accesada, datos ingresados, estado del dispositivo donde opera, etc.).

5. Utilizaría Kubernetes en alguna nube (gcp, aws, azure, etc), con reglas de escalado automático según uso de recursos (HPA) y puedan hacer frente a la demanda. Por otra parte apoyaría la disponibilización de contenido mediante un CDN (puede ser nativo de la nube o recurrir a Cloudflare, Akamai, etc.) que ponga una capa de caché y cada request a elementos estáticos de una página sean servidos por esta entidad, dejando que el backend se preocupe de la menor cantidad de interacciones y las más importantes posibles (un inicio de sesión, un carrito, un checkout, etc). Para ya evitar colapso y asegurar con varios decimales la disponibilidad, evaluaría integrar una plataforma de encolado de usuarios y tener aún más control del tráfico del sitio.

6. Mi conocimiento con BigQuery diría que es bien básico pero hay 2 estrategias indispensables. Primero es que el SELECT * está totalmente prohibido. Segundo es el particionamiento, filtrar adecuada e inteligentemente para realizar consultas más livianas.

7. Implementaría métricas y alertas para los componentes de Pub/Sub y CloudRun. Para Pub/Sub crearía una alerta para *A* mensajes acumulados sin procesar y para *B* cantidad en errores de publicación. Para el Cloudrun crearía una regla de *C* errores del subscriber en *D* cantidad de tiempo, una para *E* como umbral de latencia en el procesamiento y una para alto consumo de recurso computacional (cpu y/o ram).

8. Como oportunidad de implementación quizás utilizar una suite de IA para no tener que hacer nada manual (por ej. la ejecución del publisher or el setup de bigquery, la gestión git, la autenticación con gcp/tf, etc.). También se podría implementar IA a un registro de venta para verificar si es íntegra o anómala (potencial fraude, algún dato inconsistente/alterado, etc). Y finalmente para uso Gemini actualmente está siendo de gran ayuda, integrarlo en Looker Studio es útil para apoyarse en tareas de analítica y, en mi caso particular, fue útil específicamente para detectar problemas con el envío de datos desde el ClourRun hacia BigQuery, por ejemplo indicándome que el schema del dataset era distinto a la data que le estaba enviando.

### Puntos Generales
Es de utilidad considerar:
- Services Accounts creadas tanto en código "sa-ventas-cloudrun" y "sa-ventas-pubsub-invoker" como las creadas manualmente "sa-github-actions-gar" y "sa-wif-tf" cuentan con los permisos más atómicos posibles.
- Recursos de CloudRun efectivamente seteados como los mínimos posibles (512mi ram y 1 vCPU).

**Para el correcto setup de la solución, hay que considerar pasos no descritos anteriormente:**
1. Primero necesitamos crear dos cuentas de servicio para nuestro CI/CD, una para GitHub y otra para Terraform, que posean los atributos necesarios para autenticarse mediante Workload Identity Federation hacia GCP.
2. Necesitamos ejecutar el script de setup BigQuery, ya que en archivos de infrastructura (terraform) sólo hacemos referencia para su integración al CloudRun como variable de entorno y a los permisos necesarios para operar los recursos relacionados.
3. Desde aquí ya es posible utilizar la solución desarrollada con los pasos descritos inicialmente :)