# KeyByMe

Gestor personal de contactos, passwords, documentos, fotos, videos y recordatorios,
con administración centralizada de usuarios y cuotas de espacio.

## Estructura del proyecto

```
keybyme/
├── config/          # Configuración global (settings, urls)
├── accounts/        # CustomUser: cuotas de espacio, roles, admin principal
├── menus/           # Módulos, submódulos, roles y permisos (menús dinámicos)
├── vault/           # Contactos, passwords cifrados, archivos, recordatorios
├── requirements.txt
├── .env.example
└── manage.py
```

## Instalación local

### 1. Requisitos previos
- Python 3.11+
- PostgreSQL instalado y corriendo (local o remoto)

### 2. Crear la base de datos en PostgreSQL

```sql
CREATE DATABASE keybyme_db;
CREATE USER keybyme_user WITH PASSWORD 'keybyme_pass';
GRANT ALL PRIVILEGES ON DATABASE keybyme_db TO keybyme_user;
```

(Cambia el usuario/password por unos seguros y actualiza el `.env` acorde.)

### 3. Entorno virtual e instalación de dependencias

```bash
python -m venv venv
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

pip install -r requirements.txt
```

### 4. Configurar variables de entorno

Copia `.env.example` a `.env` y ajusta los valores:

```bash
cp .env.example .env
```

Genera tu propia llave de cifrado (no uses la del ejemplo en producción):

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Pega el resultado en `VAULT_ENCRYPTION_KEY` dentro de `.env`.

⚠️ **Importante:** si pierdes esta llave, los passwords guardados en el vault
quedan imposibles de recuperar. Guárdala en un lugar seguro (gestor de secretos,
no en el repositorio de código).

### 5. Migraciones y superusuario

```bash
python manage.py migrate
python manage.py createsuperuser
```

Este superusuario debe marcarse como `is_admin_principal = True` desde el
Django Admin (`/admin`) para tener control total sobre otros usuarios.

### 6. Correr el servidor

```bash
python manage.py runserver
```

Abre `http://127.0.0.1:8000/admin` para gestionar usuarios, módulos, roles
y todo el contenido desde el panel de administración incluido de Django.

## Modelo de permisos (resumen)

- **Module**: sección principal del menú (Contactos, Passwords, Documentos...).
- **SubModule**: acción dentro de un módulo (Ver, Crear, Eliminar...).
- **Role**: conjunto reutilizable de permisos, asignable a varios usuarios.
- **UserPermissionOverride**: excepción puntual para un usuario específico
  (otorga o revoca un permiso sin tocar su Role).

La lógica de chequeo vive en `CustomUser.has_permission(codename)`.

## Cuotas de espacio

Cada `CustomUser` tiene `storage_quota_gb` y `storage_used_bytes`. Antes de
guardar un archivo nuevo en `vault.MediaFile`, usa `user.has_space_for(bytes)`
para validar que no exceda su cuota.

## Siguientes pasos sugeridos

- [ ] Vistas y templates (o API REST con Django REST Framework) para el panel de usuario
- [ ] Vista de login/logout personalizada
- [ ] Lógica de actualización de `storage_used_bytes` al subir archivos (señales o en la vista de upload)
- [ ] Configurar `django-storages` + S3 cuando se necesite salir de almacenamiento local
- [ ] Tests automatizados
