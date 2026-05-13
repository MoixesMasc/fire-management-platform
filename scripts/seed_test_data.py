"""Seed fake data for local testing of all microservices."""

import json
import os
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import boto3
from botocore.exceptions import ClientError

AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
DYNAMODB_ENDPOINT_URL = os.getenv("DYNAMODB_ENDPOINT_URL", "http://localhost:4566")

TABLE_CONFIG = [
    ("fire_users", "user_id"),
    ("fire_reports", "report_id"),
    ("fire_validations", "validation_id"),
]


def get_dynamodb_resource():
    kwargs: dict[str, Any] = {"region_name": AWS_REGION}
    if DYNAMODB_ENDPOINT_URL:
        kwargs["endpoint_url"] = DYNAMODB_ENDPOINT_URL
    return boto3.resource("dynamodb", **kwargs)


def table_exists(resource, table_name: str) -> bool:
    try:
        resource.Table(table_name).load()
        return True
    except ClientError as exc:
        if exc.response["Error"]["Code"] in [
            "ResourceNotFoundException",
            "ValidationException",
        ]:
            return False
        raise


def create_table(resource, table_name: str, hash_key: str) -> None:
    if table_exists(resource, table_name):
        print(f"Tabla ya existe: {table_name}")
        return

    print(f"Creando tabla: {table_name}")
    resource.create_table(
        TableName=table_name,
        KeySchema=[{"AttributeName": hash_key, "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": hash_key, "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    ).wait_until_exists()
    print(f"Tabla creada: {table_name}")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def seed_users(table):
    users = [
        {
            "user_id": "user-1",
            "email": "ana@example.com",
            "phone_number": "+15550000001",
            "latitude": "40.7128",
            "longitude": "-74.0060",
            "name": "Ana Rivera",
        },
        {
            "user_id": "user-2",
            "email": "raul@example.com",
            "phone_number": "+15550000002",
            "latitude": "40.7145",
            "longitude": "-74.0052",
            "name": "Raúl López",
        },
        {
            "user_id": "user-3",
            "email": "carla@example.com",
            "phone_number": "+15550000003",
            "latitude": "34.0522",
            "longitude": "-118.2437",
            "name": "Carla Gómez",
        },
    ]

    for user in users:
        print(f"Insertando usuario: {user['user_id']}")
        table.put_item(Item=user)


def seed_reports(table):
    reports = [
        {
            "report_id": "report-1",
            "title": "Humo visible en almacén del puerto",
            "description": "Se observan columnas de humo cerca del almacén de cargas.",
            "location": json.dumps({"latitude": 40.7130, "longitude": -74.0070}),
            "severity": "high",
            "status": "pending",
            "reporter_id": "user-1",
            "created_at": now_iso(),
            "updated_at": now_iso(),
            "image_s3_key": "images/report-1.jpg",
        },
        {
            "report_id": "report-2",
            "title": "Incendio forestal en colinas cercanas",
            "description": "Se detectó un incendio de maleza en la zona norte.",
            "location": json.dumps({"latitude": 34.0522, "longitude": -118.2437}),
            "severity": "critical",
            "status": "validated",
            "reporter_id": "user-3",
            "created_at": now_iso(),
            "updated_at": now_iso(),
            "image_s3_key": "images/report-2.jpg",
        },
        {
            "report_id": "report-3",
            "title": "Residuos ardientes en estacionamiento",
            "description": "Se quemaron residuos sólidos en un estacionamiento comercial.",
            "location": json.dumps({"latitude": 40.7135, "longitude": -74.0050}),
            "severity": "medium",
            "status": "rejected",
            "reporter_id": "user-2",
            "created_at": now_iso(),
            "updated_at": now_iso(),
        },
    ]
    for report in reports:
        print(f"Insertando reporte: {report['report_id']}")
        table.put_item(Item=report)


def seed_validations(table):
    validations = [
        {
            "validation_id": "validation-1",
            "report_id": "report-2",
            "status": "fire_confirmed",
            "s3_image_uri": "s3://fire-validation/test-report-2.jpg",
            "fire_labels": ["Fire", "Smoke"],
            "labels_count": 3,
            "validated_at": now_iso(),
            "confidence_score": "95.2",
        },
        {
            "validation_id": "validation-2",
            "report_id": "report-3",
            "status": "fire_not_detected",
            "s3_image_uri": "s3://fire-validation/test-report-3.jpg",
            "fire_labels": [],
            "labels_count": 1,
            "validated_at": now_iso(),
            "confidence_score": "79.6",
        },
    ]
    for validation in validations:
        print(f"Insertando validación: {validation['validation_id']}")
        table.put_item(Item=validation)


def main():
    print("Seed de datos ficticios para los microservicios")
    resource = get_dynamodb_resource()

    for table_name, key in TABLE_CONFIG:
        create_table(resource, table_name, key)

    seed_users(resource.Table("fire_users"))
    seed_reports(resource.Table("fire_reports"))
    seed_validations(resource.Table("fire_validations"))

    print("\nSeed completado. Ya puedes probar los microservicios con datos ficticios.")
    print("Usuarios insertados: 3")
    print("Reportes insertados: 3")
    print("Validaciones insertadas: 2")


if __name__ == "__main__":
    main()
