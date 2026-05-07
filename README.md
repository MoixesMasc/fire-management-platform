# Fire Management Platform

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Pydantic](https://img.shields.io/badge/Pydantic-v2-E92063?style=flat&logo=pydantic&logoColor=white)](https://docs.pydantic.dev/)
[![Tests](https://github.com/MoixesMasc/fire-management-platform/actions/workflows/tests.yml/badge.svg)](https://github.com/MoixesMasc/fire-management-platform/actions/workflows/tests.yml)
[![Coverage](https://img.shields.io/badge/coverage-87%25-4CAF50?style=flat&logo=codecov&logoColor=white)](https://github.com/MoixesMasc/fire-management-platform)
[![AWS Lambda](https://img.shields.io/badge/AWS-Lambda-FF9900?style=flat&logo=awslambda&logoColor=white)](https://aws.amazon.com/lambda/)
[![DynamoDB](https://img.shields.io/badge/AWS-DynamoDB-4053D6?style=flat&logo=amazondynamodb&logoColor=white)](https://aws.amazon.com/dynamodb/)
[![Docker](https://img.shields.io/badge/Docker-Alpine-2496ED?style=flat&logo=docker&logoColor=white)](https://www.docker.com/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000?style=flat&logo=python&logoColor=white)](https://github.com/psf/black)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue?style=flat)](LICENSE)
[![GitHub last commit](https://img.shields.io/github/last-commit/MoixesMasc/fire-management-platform?style=flat&logo=github)](https://github.com/MoixesMasc/fire-management-platform/commits/master)

Plataforma de gestión de incendios basada en microservicios independientes sobre AWS, construida con FastAPI, DynamoDB y servicios gestionados de AWS.

---

## Arquitectura

```
┌─────────────────────────────────────────────────────────────────┐
│                        API Gateway / ALB                        │
└──────────┬──────────────┬──────────────┬────────────────────────┘
           │              │              │
    ┌──────▼──────┐ ┌─────▼──────┐ ┌───▼──────────────┐
    │   Users     │ │ Incidents  │ │ Fire Validation  │
    │  (Lambda)   │ │  (Lambda)  │ │   (EC2/Docker)   │
    │  :8001      │ │  :8002     │ │   :8003          │
    └──────┬──────┘ └─────┬──────┘ └───┬──────────────┘
           │              │            │
    ┌──────▼──────────────▼────────────▼──────────────┐
    │                   DynamoDB                       │
    │   fire_users │ fire_reports │ fire_validations   │
    └────────────────────┬────────────────────────────┘
                         │ DynamoDB Streams
                  ┌──────▼───────┐
                  │ Notifications│
                  │   (Lambda)   │
                  └──────┬───────┘
                    ┌────┴────┐
                  SNS       SES
```

---

## Microservicios

### 1. Users Service — `services/users/` (Lambda)
Gestión de usuarios y autenticación via **AWS Cognito**.

| Método | Ruta | Descripción |
|--------|------|-------------|
| POST | `/auth/signup` | Registrar nuevo usuario |
| POST | `/auth/login` | Autenticarse y obtener tokens JWT |
| POST | `/auth/refresh` | Renovar access token |

### 2. Incidents Service — `services/incidents/` (Lambda)
CRUD de reportes de incendio con persistencia en **DynamoDB**.

| Método | Ruta | Descripción |
|--------|------|-------------|
| POST | `/reports` | Crear reporte de incendio |
| GET | `/reports` | Listar reportes con filtros y paginación |

**Filtros disponibles:** `severity` (low/medium/high/critical), `status` (pending/validated/rejected/resolved), `limit`, `next_token`

### 3. Fire Validation Service — `services/fire_validation/` (EC2/Docker)
Valida imágenes de incendios usando **AWS Rekognition** y actualiza el estado del reporte.

| Método | Ruta | Descripción |
|--------|------|-------------|
| POST | `/validate` | Analizar imagen S3 con Rekognition |

**Flujo:** recibe `s3_bucket` + `s3_key` → llama a Rekognition → guarda resultado en DynamoDB → actualiza estado del reporte padre.

### 4. Notifications Service — `services/notifications/` (Lambda)
Trigger asíncrono desde **DynamoDB Streams**. Calcula usuarios en radio de 5km usando la fórmula Haversine y envía alertas via **SNS** y **SES**.

**Flujo:** DynamoDB Stream (INSERT fire_confirmed) → calcula radio 5km → SNS broadcast + SES email por usuario cercano.

---

## Stack Tecnológico

| Capa | Tecnología |
|------|-----------|
| Lenguaje | Python 3.11+ |
| Framework | FastAPI 0.115+ (asyncio) |
| Base de datos | DynamoDB (boto3 directo, sin ORM) |
| Validación | Pydantic v2 |
| Auth | JWT via AWS Cognito JWKS |
| Logging | Structlog (JSON estructurado) |
| Deploy Lambda | Mangum |
| Deploy EC2 | Docker (Alpine Python multi-stage) |
| Testing | Pytest + pytest-asyncio (cobertura >87%) |
| Local dev | DynamoDB Local (Docker) |

---

## Estructura del Proyecto

```
fire-management-platform/
├── shared/                        # Módulo compartido entre servicios
│   ├── auth.py                    # Validación JWT via Cognito JWKS
│   ├── dynamodb.py                # Conexión boto3 + helpers
│   └── logging_config.py          # Structlog JSON
│
├── services/
│   ├── users/
│   │   ├── main.py                # FastAPI app + Mangum handler
│   │   ├── models.py              # Pydantic: SignUp, Login, Refresh
│   │   ├── router.py              # Rutas /auth/*
│   │   ├── cognito_service.py     # SDK Cognito
│   │   ├── requirements.txt
│   │   └── tests/
│   │
│   ├── incidents/
│   │   ├── main.py
│   │   ├── models.py              # Pydantic: CreateReport, GeoLocation
│   │   ├── router.py              # Rutas /reports
│   │   ├── dynamodb_service.py    # put_item + scan con paginación
│   │   ├── requirements.txt
│   │   └── tests/
│   │
│   ├── fire_validation/
│   │   ├── main.py
│   │   ├── models.py              # Pydantic: ValidateRequest/Response
│   │   ├── router.py              # Ruta /validate
│   │   ├── rekognition_service.py # detect_labels + mapeo de status
│   │   ├── dynamodb_service.py    # Persistencia de resultados
│   │   ├── Dockerfile             # Multi-stage Alpine Python
│   │   ├── requirements.txt
│   │   └── tests/
│   │
│   └── notifications/
│       ├── handler.py             # Lambda entry point + asyncio.gather
│       ├── models.py              # FireAlert, NearbyUser
│       ├── geo_service.py         # Haversine 5km + scan usuarios
│       ├── notification_service.py# SNS publish + SES HTML email
│       ├── requirements.txt
│       └── tests/
│
├── conftest.py                    # Config global pytest
├── pytest.ini                     # Paths, asyncio_mode, marcadores
├── docker-compose.yml             # Stack local con DynamoDB Local
└── .env.example                   # Variables de entorno documentadas
```

---

## Inicio Rápido

### Prerrequisitos

- Python 3.11+
- Docker Desktop
- AWS CLI configurado (o credenciales en `.env`)

### 1. Clonar y configurar entorno

```bash
git clone https://github.com/MoixesMasc/fire-management-platform.git
cd fire-management-platform

python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/Mac
source .venv/bin/activate

pip install -r services/users/requirements.txt
```

### 2. Configurar variables de entorno

```bash
cp .env.example .env
# Editar .env con tus valores de AWS Cognito
```

### 3. Levantar DynamoDB Local

```bash
docker run -d --name dynamodb-local -p 8000:8000 \
  amazon/dynamodb-local:latest \
  -jar DynamoDBLocal.jar -inMemory -sharedDb
```

### 4. Crear las tablas

```bash
python - << 'EOF'
import boto3
db = boto3.client('dynamodb', region_name='us-east-1',
    endpoint_url='http://localhost:8000',
    aws_access_key_id='test', aws_secret_access_key='test')
for table, key in [('fire_reports','report_id'), ('fire_validations','validation_id'), ('fire_users','user_id')]:
    db.create_table(TableName=table,
        KeySchema=[{'AttributeName': key, 'KeyType': 'HASH'}],
        AttributeDefinitions=[{'AttributeName': key, 'AttributeType': 'S'}],
        BillingMode='PAY_PER_REQUEST')
    print(f'Tabla creada: {table}')
EOF
```

### 5. Arrancar servicios

```bash
# Users Service
PYTHONPATH=. uvicorn services.users.main:app --port 8001 --reload

# Incidents Service
PYTHONPATH=. uvicorn services.incidents.main:app --port 8002 --reload

# Fire Validation Service
PYTHONPATH=. uvicorn services.fire_validation.main:app --port 8003 --reload
```

### 6. Verificar health checks

```bash
curl http://localhost:8001/health  # {"status":"ok","service":"users"}
curl http://localhost:8002/health  # {"status":"ok","service":"incidents"}
curl http://localhost:8003/health  # {"status":"ok","service":"fire_validation"}
```

---

## Documentación de la API

Cada servicio expone documentación interactiva Swagger una vez arrancado:

| Servicio | Swagger UI | ReDoc |
|----------|-----------|-------|
| Users | http://localhost:8001/docs | http://localhost:8001/redoc |
| Incidents | http://localhost:8002/docs | http://localhost:8002/redoc |
| Fire Validation | http://localhost:8003/docs | http://localhost:8003/redoc |

---

## Ejemplos de Uso

### Registrar usuario

```bash
curl -X POST http://localhost:8001/auth/signup \
  -H "Content-Type: application/json" \
  -d '{
    "email": "bombero@ejemplo.com",
    "password": "Segura!123",
    "full_name": "Carlos Ruiz",
    "phone_number": "+34612345678"
  }'
```

### Crear reporte de incendio

```bash
curl -X POST http://localhost:8002/reports \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Incendio forestal en Sierra Norte",
    "description": "Columna de humo visible, llamas activas avanzando al norte.",
    "location": { "latitude": 37.7749, "longitude": -3.7826 },
    "severity": "critical",
    "image_s3_key": "uploads/incendio_001.jpg"
  }'
```

### Listar reportes con filtros

```bash
# Filtrar por severidad crítica, máximo 10 resultados
curl "http://localhost:8002/reports?severity=critical&limit=10" \
  -H "Authorization: Bearer <token>"
```

### Validar imagen con Rekognition

```bash
curl -X POST http://localhost:8003/validate \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "s3_bucket": "fire-platform-images",
    "s3_key": "uploads/incendio_001.jpg",
    "report_id": "rpt-uuid-aqui",
    "min_confidence": 80.0
  }'
```

---

## Tests

```bash
# Correr todos los tests
pytest services/ -v

# Con reporte de cobertura
pytest services/ --cov=services --cov=shared --cov-report=term-missing

# Solo un servicio
pytest services/incidents/ -v

# Solo tests unitarios (sin integración)
pytest services/ -m "not integration" -v
```

**Cobertura actual: 87%** (52 tests, objetivo >80%)

---

## Variables de Entorno

| Variable | Descripción | Ejemplo |
|----------|-------------|---------|
| `AWS_REGION` | Región AWS | `us-east-1` |
| `COGNITO_USER_POOL_ID` | ID del User Pool de Cognito | `us-east-1_XXXXXXXXX` |
| `COGNITO_CLIENT_ID` | ID del App Client | `abc123...` |
| `COGNITO_CLIENT_SECRET` | Secret del App Client (opcional) | `xyz...` |
| `REPORTS_TABLE` | Nombre tabla DynamoDB de reportes | `fire_reports` |
| `VALIDATIONS_TABLE` | Nombre tabla DynamoDB de validaciones | `fire_validations` |
| `USERS_TABLE` | Nombre tabla DynamoDB de usuarios | `fire_users` |
| `DYNAMODB_ENDPOINT_URL` | URL local para desarrollo | `http://localhost:8000` |
| `SNS_FIRE_ALERTS_TOPIC_ARN` | ARN del topic SNS de alertas | `arn:aws:sns:...` |
| `SES_SENDER_EMAIL` | Email remitente SES verificado | `alerts@dominio.com` |
| `NOTIFICATION_RADIUS_KM` | Radio de notificación en km | `5.0` |
| `LOG_LEVEL` | Nivel de logging | `INFO` |

---

## Deploy

### Lambda (Users, Incidents, Notifications)

Cada servicio usa **Mangum** como adaptador WSGI para AWS Lambda:

```python
from mangum import Mangum
handler = Mangum(app, lifespan="off")
```

El `handler` es el entry point configurado en la función Lambda.

### EC2/Docker (Fire Validation)

```bash
# Build
docker build -f services/fire_validation/Dockerfile -t fire-validation:latest .

# Run
docker run -p 8003:8000 \
  -e AWS_REGION=us-east-1 \
  -e AWS_ACCESS_KEY_ID=... \
  -e AWS_SECRET_ACCESS_KEY=... \
  fire-validation:latest
```

---

## Licencia

MIT
