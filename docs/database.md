# Arquitectura de Base de Datos - Wardogs

## Modelo Entidad-Relación (ER)

El siguiente diagrama muestra cómo se relacionan las diferentes entidades dentro de la base de datos MySQL usando SQLModel.

```mermaid
erDiagram
    PLAYER ||--o{ PLAYER_ROLE : "has"
    ROLE ||--o{ PLAYER_ROLE : "assigned to"
    PLAYER ||--o{ MEMBERSHIP : "subscribes"
    ROLE ||--o{ MEMBERSHIP : "grants"
    PLAYER ||--o{ MATCH_PLAYER_STATS : "participates in"
    MATCH ||--o{ MATCH_PLAYER_STATS : "records"
    TEAM ||--o{ MATCH_PLAYER_STATS : "plays for"
    MATCH ||--o{ MATCH_TEAM_STATS : "records"
    TEAM ||--o{ MATCH_TEAM_STATS : "belongs to"
    TEAM ||--o{ MATCH : "wins"

    PLAYER {
        string steam_id PK
        string discord_id UK "Opcional, usado al vincular"
        string custom_welcome_message "Requiere rol VIP/ADMIN para usarse"
    }

    ROLE {
        int id PK
        string name UK "Ej. ADMIN, MODERATOR, VIP, VIP_FUNDADOR, NITRO_1"
    }

    PLAYER_ROLE {
        string steam_id PK, FK
        int role_id PK, FK
    }

    MEMBERSHIP {
        int id PK
        string steam_id FK
        int role_granted_id FK "El rol que da esta membresía (ej. VIP)"
        string type "VIP_MENSUAL, VIP_QUINCENAL, LIFETIME"
        datetime start_date
        datetime end_date "NULL si es LIFETIME"
        boolean is_active "Campo bandera (bandera lógica o computada)"
    }

    TEAM {
        int id PK
        string name UK "Lonestar, Manticore, Valkyre"
        string code UK "BLU, GRN, RED"
    }

    MATCH {
        string id PK "UUID Generado por la API"
        string map_name
        datetime start_time
        datetime end_time
        int winning_team_id FK "Opcional"
    }

    MATCH_TEAM_STATS {
        string match_id PK, FK
        int team_id PK, FK
        int score
    }

    MATCH_PLAYER_STATS {
        string steam_id PK, FK
        string match_id PK, FK
        int team_id FK "Opcional"
        int kills
        int deaths
        int cash_spent
    }
```

## Explicación de Conceptos

1. **RBAC (Role-Based Access Control)**
   - `roles` es la lista de permisos básicos. Un `Player` puede tener varios roles gracias a `player_roles`. Esto permite que alguien sea `ADMIN` y a la vez `VIP_FUNDADOR`.
2. **Membresías (Suscripciones)**
   - `memberships` registra los pagos o suscripciones, incluyendo el *rol que otorgan*. Una persona puede tener 3 meses pagados representados como 3 filas de membresía secuenciales de 30 días, asegurando un historial financiero claro sin romper los permisos actuales. 
   - Las membresías permanentes (como las de los ADMIN) pueden guardarse con tipo `LIFETIME` y `end_date` nulo.
3. **Partidas Históricas**
   - Wardogs no provee IDs de partida nativos, por lo que la API es la que genera un identificador único (UUID). Este UUID enlaza el desempeño global de la partida (`matches`), el desempeño de cada equipo (`match_team_stats`) y el desempeño individual (`match_player_stats`).
