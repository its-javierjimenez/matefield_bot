El objetivo es crear una automatizacion de Wardogs, para controlar el RCON del servidor.
Esto mediante un BOT de discord utilizando hikari-crescent y una API dedicada que se conectara al servidor de RCON, esta API estaria separada del bot y serviria como un puente entre el servidor y el bot.

Python lo manejaremos mediante UV

Se debe:
Poder crear pruebas mediante mocks (servidor emulado).
LA API DEBE ESTAR COMPLETAMENTE VERSIONADA USANDO FASTAPI y PYDANTIC
EL POOLING DE LA API AL RCON ES DE 10s

Durante una partida:
Poder consultar cuantos jugadores hay en la sesion y por equipo
Poder consultar la leaderboard

Historico y duante la partida actual:
Poder consultar cuanto ha gastado un jugador, toda la sesion y un equipo
Poder consultar estadisticas de un jugador o su equipo

Poder consultar los event logs
Poder editar la cantidad de espacios reservados maxima (10 reservados maximo) (90 jugadores publicos)
Poder consultar los usuarios en espacios reservados
Poder editar los usuarios en espacios reservados (agregar o quitar)
Poder enviar un anuncio al servidor rcon

Mediante SQLITE vincular a usuarios de discord con sus cuentas de steam mediante un comando.
Guardar en la DB quienes son vip en el server y quienes son admin (sirve para identificar los espacios reservados y hacer management de usuarios pago)

Poder elegir que rol accede a cada comando.

Aquellos con el rol de ADMIN pueden usar todos los comandos

Aquellos con roles basicos pueden unicamente consultar (excepto event logs), vincular su cuenta, pero no modificar.

Aquellos con rol de VIP pueden editar que mensaje el servidor enviará cuando este se una a la sesión y vincular sus cuentas de steam. No podran modificar nada más.

Pueden llegar a haber mas de un rol admin y un rol VIP (estos podrian llegar a tener más tiers).

Se requiere una automatizacion que al terminar la partida (un equipo llega a 100) se le regale un vip por 1 dia a la persona que quedó primera en la leaderboard y se anuncia en el server de discord (canal a especificar) y en el de rcon (si ya tenia no pasa nada)