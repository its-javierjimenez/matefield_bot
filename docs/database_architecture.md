# Arquitectura de Base de Datos: MySQL y SQLModel

## ¿Qué se está haciendo?
Estamos migrando la persistencia de datos de la API desde SQLite (usando sentencias SQL crudas a través de `aiosqlite`) hacia **MySQL** utilizando **SQLModel**, que es un ORM moderno diseñado específicamente para trabajar en sincronía con FastAPI.

## ¿Qué se usa?
- **SQLModel**: Librería construida encima de **SQLAlchemy** (para la manipulación e interacción con la base de datos) y **Pydantic** (para la validación y estructuración de datos). 
- **PyMySQL**: El driver (conector) síncrono oficial usado por debajo para comunicarse con el servidor de MySQL.
- **FastAPI Dependency Injection (`Depends`)**: Usado para proveer una sesión (conexión de la DB) a los endpoints automáticamente.

## ¿Por qué SQLModel?
SQLModel fue creado por Sebastián Ramírez (creador de FastAPI) para combinar la potencia de los modelos Pydantic que usamos en los endpoints, con los modelos de base de datos de SQLAlchemy, ¡usando la misma clase!

## ¿Cómo se usa?

### 1. Definición de Modelos (Tablas)
Un modelo se define heredando de `SQLModel` y agregando `table=True`. Las propiedades de la clase se convierten en columnas de la base de datos.
```python
from sqlmodel import SQLModel, Field
from typing import Optional

class User(SQLModel, table=True):
    __tablename__ = "users" # Opcional: define el nombre de la tabla
    discord_id: str = Field(primary_key=True)
    steam_id: str = Field(unique=True, index=True)
    vip_expiry: Optional[datetime] = Field(default=None)
```

### 2. Inyección de Sesión en Endpoints
En lugar de crear y cerrar manualmente la base de datos, usamos la dependencia `get_session` en los endpoints de FastAPI:
```python
from sqlmodel import Session
from fastapi import Depends

@router.get("/users/{discord_id}")
def get_user(discord_id: str, session: Session = Depends(get_session)):
    # ... uso de la sesión ...
```

### 3. Operaciones CRUD Básicas

**Leer por Primary Key (GET)**
```python
user = session.get(User, discord_id)
```

**Leer usando Filtros Avanzados (SELECT)**
```python
from sqlmodel import select

statement = select(User).where(User.steam_id == "76561198000000000")
user = session.exec(statement).first() # Retorna el primero o None
```

**Insertar o Actualizar (POST/PUT)**
Para insertar un registro nuevo, o actualizar uno modificado en memoria:
```python
# Insertar nuevo
new_user = User(discord_id="123", steam_id="abc")
session.add(new_user)
session.commit() # ¡Importante! Sin commit no se guarda en la DB

# Modificar existente
user.steam_id = "xyz"
session.add(user)
session.commit()
```

## Configuración y Variables de Entorno
Para que todo funcione, es **esencial** tener definida la variable `DATABASE_URL` en tu archivo `.env`. Al usar `pymysql`, el formato debe ser:
```env
DATABASE_URL=mysql+pymysql://<usuario>:<contraseña>@<host>:<puerto>/<nombre_db>
```
Ejemplo local:
```env
DATABASE_URL=mysql+pymysql://root:password@127.0.0.1:3306/wardogs
```
