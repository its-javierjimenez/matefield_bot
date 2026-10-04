## [1.5.1] - 2026-10-04

### Corregido
- **Transparencia Financiera (UX/API)**:
  - Se modificó la capa de servicio de la API (`MembershipTypesService`) para que el almacenamiento de dinero en centavos (`int`) sea completamente transparente para los clientes. Ahora la API recibe y entrega flotantes limpios (ej: `6.0`) y maneja la conversión a centavos internamente, garantizando que el usuario final y los administradores de Discord sigan viendo los precios "como dólares comunes".
  - Se eliminaron las opciones de comandos de Discord obsoletas que hacían referencia al antiguo `base_price` (comisiones de Tebex).
