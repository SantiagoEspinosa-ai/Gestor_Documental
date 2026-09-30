"""
Crea (o reemplaza) un usuario de la aplicacion. Responsable: PERSONA_1.

La contrasena nunca va como argumento (quedaria en el historial de la terminal): se pide por
teclado, o se lee de la variable de entorno NUEVA_CONTRASENA si existe (para automatizar).
Solo contrasenas ficticias de desarrollo; nunca se guardan en el repo.

Uso local, desde backend/ (usa el .env de la raiz del repo):
    PYTHONPATH=. python ../scripts/crear_usuario.py --usuario revisor_demo --rol revisor

Uso en Docker (scripts/ no esta montado en el contenedor; se monta solo para esta ejecucion):
    docker compose run --rm -v ./scripts:/scripts -e PYTHONPATH=/app backend \
        python /scripts/crear_usuario.py --usuario admin_demo --rol admin

Anade --reemplazar para cambiar la contrasena y el rol de un usuario que ya existe.
"""
import argparse
import getpass
import os
import sys

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import SesionLocal, get_engine
from app.core.modelos import ROLES, Usuario
from app.core.seguridad import hash_contrasena

MIN_CARACTERES = 8


def crear_usuario(sesion: Session, usuario: str, rol: str, contrasena: str,
                  reemplazar: bool = False) -> Usuario:
    """Crea el usuario con la contrasena en hash bcrypt. ValueError si no se puede."""
    if rol not in ROLES:
        raise ValueError(f"Rol no valido: {rol}. Usa uno de {', '.join(ROLES)}")
    if len(contrasena) < MIN_CARACTERES:
        raise ValueError(f"La contrasena debe tener al menos {MIN_CARACTERES} caracteres")

    fila = sesion.scalar(select(Usuario).where(Usuario.usuario == usuario))
    if fila and not reemplazar:
        raise ValueError(f"El usuario '{usuario}' ya existe; usa --reemplazar para cambiarlo")
    fila = fila or Usuario(usuario=usuario)
    fila.rol = rol
    fila.hash_contrasena = hash_contrasena(contrasena)
    sesion.add(fila)
    sesion.commit()
    return fila


def main() -> int:
    parser = argparse.ArgumentParser(description="Crea un usuario de la aplicacion.")
    parser.add_argument("--usuario", required=True)
    parser.add_argument("--rol", required=True, choices=ROLES)
    parser.add_argument("--reemplazar", action="store_true", help="reemplaza un usuario existente")
    args = parser.parse_args()

    contrasena = os.environ.get("NUEVA_CONTRASENA") or getpass.getpass("Contrasena: ")
    with SesionLocal(bind=get_engine()) as sesion:
        try:
            crear_usuario(sesion, args.usuario, args.rol, contrasena, args.reemplazar)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
    print(f"Usuario '{args.usuario}' guardado con rol {args.rol}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
