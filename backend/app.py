from flask import Flask, send_from_directory, request, jsonify, make_response
from flask_cors import CORS
import csv
import uuid  # Para generar tokens únicos
import secrets
from decimal import Decimal
from dotenv import load_dotenv
import os
import requests
from flask import send_file
from reportlab.lib.pagesizes import letter, landscape
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.utils import simpleSplit  # Añadimos esta importación
from io import TextIOWrapper, BytesIO
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from sqlalchemy.sql import text
from sqlalchemy.orm import aliased  # Importar aliased
from sqlalchemy.sql import func
from zoneinfo import ZoneInfo
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm import Session
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy import create_engine, func, case, select
from werkzeug.security import generate_password_hash
from werkzeug.security import check_password_hash
from models import (
    db, SesionActiva, Usuario, Producto, Bodega, InventarioBodega, Movimiento, Venta, 
    EstadoInventario, RegistroMovimientos, MaterialProducto, 
    OrdenProduccion, DetalleProduccion, EntregaParcial, AjusteInventarioDetalle, Kardex
)
# Añadir al inicio después de los imports
import logging
import json  # Añadimos json para el serializador
import pytz


# Configurar logging para Railway
#logging.basicConfig(
#    level=logging.DEBUG,
#    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
#    handlers=[logging.StreamHandler()]  # Enviar logs a stdout
#)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Forzar salida sin buffering para Gunicorn
import sys
if not sys.stdout.isatty():  # Detectar entorno de producción
    sys.stdout = sys.stderr = open('/dev/stdout', 'w', buffering=1)


# Cargar variables del archivo .env
load_dotenv()

# Construir la URI de la base de datos desde variables individuales
PGHOST = os.getenv('PGHOST')
PGDATABASE = os.getenv('PGDATABASE')
PGUSER = os.getenv('PGUSER')
PGPASSWORD = os.getenv('PGPASSWORD')
PGPORT = os.getenv('PGPORT')
# Construir la URI de conexión
DATABASE_URI = f"postgresql+psycopg2://{PGUSER}:{PGPASSWORD}@{PGHOST}:{PGPORT}/{PGDATABASE}"


def obtener_hora_utc():
    """Obtiene la hora actual en UTC."""
    return datetime.now(timezone.utc)

def obtener_hora_colombia():
    """Obtiene la hora actual en la zona horaria de Colombia sin zona horaria."""
    return datetime.now(ZoneInfo("America/Bogota")).replace(tzinfo=None)

def convertir_a_hora_colombia(fecha_utc):
    """Convierte una fecha UTC a la hora local de Colombia."""
    if fecha_utc:
        return fecha_utc.astimezone(ZoneInfo('America/Bogota'))
    return None

# Prueba inicial para verificar las funciones de hora
def prueba_horas():
    print("\n=== PRUEBA DE HORAS ===")
    hora_utc = obtener_hora_utc()
    print(f"HORA UTC: {hora_utc} (tipo: {type(hora_utc)})")

    hora_colombia = obtener_hora_colombia(hora_utc)
    print(f"HORA COLOMBIA: {hora_colombia} (tipo: {type(hora_colombia)})")
    print("========================\n")



# Parametros de Usuarios y cantidadd de sesiones concurrentes permitidas
# Usar las variables de entorno
MAX_USUARIOS = int(os.getenv('MAX_USUARIOS', 5))  # Valor por defecto: 5
MAX_SESIONES_CONCURRENTES = int(os.getenv('MAX_SESIONES_CONCURRENTES', 3))  # Valor por defecto: 3

def generate_token():
    """
    Genera un token único y seguro para sesiones activas.
    """
    return secrets.token_hex(32)  # Genera un token hexadecimal de 64 caracteres


def calcular_inventario_producto(producto_id):
    try:
        inventarios = db.session.query(
            EstadoInventario.bodega_id,
            EstadoInventario.cantidad,
            Bodega.nombre.label('bodega_nombre')
        ).join(Bodega, EstadoInventario.bodega_id == Bodega.id
        ).filter(EstadoInventario.producto_id == producto_id).all()

        resultado = [
            {
                'bodega': inv.bodega_nombre,
                'cantidad': inv.cantidad
            }
            for inv in inventarios
        ]
        return resultado
    except Exception as e:
        print(f"Error en calcular_inventario_producto: {str(e)}")
        return []

def actualizar_estado_inventario(producto_id, bodega_id, cantidad, es_entrada=True):
    try:
        inventario = EstadoInventario.query.filter_by(producto_id=producto_id, bodega_id=bodega_id).first()
        cantidad = float(cantidad)
        if inventario:
            if es_entrada:
                inventario.cantidad += cantidad
            else:
                inventario.cantidad -= cantidad
            inventario.ultima_actualizacion = obtener_hora_colombia()
        else:
            inventario = EstadoInventario(
                producto_id=producto_id,
                bodega_id=bodega_id,
                cantidad=cantidad if es_entrada else -cantidad,
                ultima_actualizacion=obtener_hora_colombia(),
                costo_unitario=0.0,
                costo_total=0.0
            )
            db.session.add(inventario)

        ultimo_kardex = Kardex.query.filter_by(
            producto_id=producto_id,
            bodega_destino_id=bodega_id
        ).order_by(Kardex.fecha.desc()).first()
        if ultimo_kardex:
            inventario.costo_unitario = float(ultimo_kardex.saldo_costo_unitario)
            inventario.costo_total = inventario.cantidad * inventario.costo_unitario
        # No commit aquí, se hace en el endpoint
    except Exception as e:
        print(f"Error al actualizar estado_inventario: {str(e)}")
        raise  # Propagar error al endpoint

# Función para generar consecutivo que escribe en tabla registro_movimientos
def generar_consecutivo():
    ultimo_consecutivo = db.session.query(
        db.func.max(db.cast(RegistroMovimientos.consecutivo, db.String))
    ).scalar() or "T00000"
    try:
        return f"T{int(ultimo_consecutivo[1:]) + 1:05d}"
    except ValueError:
        return "T00001"
    
def registrar_entrega_parcial_logic(orden_id, cantidad_entregada, comentario):
    """Registra una entrega parcial o total, actualiza inventarios y movimientos."""
    # Obtener la orden de producción
    orden = db.session.get(OrdenProduccion, orden_id)
    if not orden or orden.estado not in ["En Producción", "En Producción-Parcial"]:
        raise ValueError("La orden no está en estado válido para registrar producción.")

    # Registrar la entrega
    nueva_entrega = EntregaParcial(
        orden_produccion_id=orden.id,
        cantidad_entregada=cantidad_entregada,
        fecha_entrega=obtener_hora_colombia(),
        comentario=comentario
    )
    db.session.add(nueva_entrega)

    producto_id = orden.producto_compuesto_id
    bodega_origen_id = orden.bodega_produccion_id
    bodega_destino_id = orden.bodega_produccion_id  # 🔹 Se mantiene en la misma bodega de producción

    # Descontar materiales utilizados en la producción
    materiales_producto = db.session.query(MaterialProducto).filter_by(
        producto_compuesto_id=producto_id
    ).all()
    for material in materiales_producto:
        cantidad_requerida = material.cantidad * cantidad_entregada
        estado_material = EstadoInventario.query.filter_by(
            bodega_id=bodega_origen_id, producto_id=material.producto_base_id
        ).first()

        if not estado_material or estado_material.cantidad < cantidad_requerida:
            raise ValueError(f"Inventario insuficiente de producto {material.producto_base_id} "
                             f"en la bodega de producción. Requerido: {cantidad_requerida}, "
                             f"Disponible: {estado_material.cantidad if estado_material else 0}")

        estado_material.cantidad -= cantidad_requerida
        estado_material.ultima_actualizacion = obtener_hora_colombia()

        # Registrar movimiento de salida para cada material
        movimiento_salida_material = RegistroMovimientos(
            consecutivo=generar_consecutivo(),
            tipo_movimiento='SALIDA',
            producto_id=material.producto_base_id,
            bodega_origen_id=bodega_origen_id,
            bodega_destino_id=None,
            cantidad=cantidad_requerida,
            fecha=obtener_hora_colombia(),
            descripcion=f"Salida de mercancía para creación producto con orden de producción {orden.numero_orden}."
        )
        db.session.add(movimiento_salida_material)

    # Actualizar inventario del producto compuesto
    estado_destino = EstadoInventario.query.filter_by(
        bodega_id=bodega_destino_id, producto_id=producto_id
    ).first()
    if not estado_destino:
        estado_destino = EstadoInventario(
            bodega_id=bodega_destino_id,
            producto_id=producto_id,
            cantidad=0,
            ultima_actualizacion=obtener_hora_colombia()
        )
        db.session.add(estado_destino)
    estado_destino.cantidad += cantidad_entregada
    estado_destino.ultima_actualizacion = obtener_hora_colombia()

    # Calcular cantidad pendiente
    entregas_totales = db.session.query(func.sum(EntregaParcial.cantidad_entregada)).filter_by(
        orden_produccion_id=orden.id
    ).scalar() or 0
    cantidad_pendiente = orden.cantidad_paquetes - entregas_totales

    if cantidad_pendiente <= 0:  # Producción completa
        descripcion = f"Producción completa registrada para la orden {orden.numero_orden}."
    else:  # Producción parcial
        descripcion = f"Producción parcial registrada para la orden {orden.numero_orden}."

    # Registrar movimiento de entrada del producto compuesto
    movimiento_entrada = RegistroMovimientos(
        consecutivo=generar_consecutivo(),
        tipo_movimiento='ENTRADA',
        producto_id=producto_id,
        bodega_origen_id=bodega_origen_id,
        bodega_destino_id=bodega_destino_id,  # 🔹 Se mantiene en la misma bodega de producción
        cantidad=cantidad_entregada,
        fecha=obtener_hora_colombia(),
        descripcion=descripcion
    )
    db.session.add(movimiento_entrada)

    db.session.commit()


# Función para calcular el inventario basado en movimientos
def calcular_inventario_por_bodega(producto_id):
    """Calcula el inventario por bodega usando los movimientos."""
    inventario = {}

    movimientos = db.session.query(
        Movimiento.bodega_destino_id.label('bodega_id'),
        func.sum(case([(Movimiento.tipo_movimiento == 'ENTRADA', Movimiento.cantidad)], else_=0)).label('entradas'),
        func.sum(case([(Movimiento.tipo_movimiento == 'VENTA', Movimiento.cantidad)], else_=0)).label('ventas'),
        func.sum(case([(Movimiento.tipo_movimiento == 'TRASLADO', Movimiento.cantidad)], else_=0)).label('traslados_entrantes'),
        func.sum(case([(Movimiento.tipo_movimiento == 'TRASLADO', Movimiento.cantidad)], else_=0)).label('traslados_salientes')
    ).filter(Movimiento.producto_id == producto_id).group_by(Movimiento.bodega_destino_id).all()

    for movimiento in movimientos:
        bodega = Bodega.db.session.get(movimiento.bodega_id)
        if not bodega:
            continue

        entradas = movimiento.entradas or 0
        ventas = movimiento.ventas or 0
        traslados_entrantes = movimiento.traslados_entrantes or 0
        traslados_salientes = movimiento.traslados_salientes or 0

        inventario[bodega.nombre] = entradas + traslados_entrantes - ventas - traslados_salientes

    return inventario

def consultar_kardex(producto_id):
    """Genera el kardex del producto con saldos actualizados por movimiento."""
    movimientos = db.session.query(
        Movimiento.fecha,
        Movimiento.tipo_movimiento,
        Movimiento.cantidad,
        db.case(
            (Movimiento.tipo_movimiento == 'ENTRADA', 'Compra de producto con Factura ' + Movimiento.descripcion),
            (Movimiento.tipo_movimiento == 'VENTA', 'Venta con Factura ' + Movimiento.descripcion),
            (Movimiento.tipo_movimiento == 'TRASLADO', 'Traslado entre bodegas: de ' + Movimiento.bodega_origen.nombre + ' a ' + Movimiento.bodega_destino.nombre),
            else_=''
        ).label('descripcion')
    ).filter(Movimiento.producto_id == producto_id).order_by(Movimiento.fecha).all()

    saldo = 0
    kardex = []

    for movimiento in movimientos:
        if movimiento.tipo_movimiento == 'ENTRADA':
            saldo += movimiento.cantidad
        elif movimiento.tipo_movimiento == 'VENTA':
            saldo -= movimiento.cantidad

        kardex.append({
            'fecha': movimiento.fecha.strftime('%Y-%m-%d %H:%M:%S'),
            'tipo': movimiento.tipo_movimiento,
            'cantidad': movimiento.cantidad,
            'saldo': saldo if movimiento.tipo_movimiento != 'TRASLADO' else None,
            'descripcion': movimiento.descripcion
        })

    return kardex

# Función para generar el kardex
def generar_kardex(producto_id):
    """Genera el kardex de un producto."""
    movimientos = db.session.query(
        Movimiento.fecha,
        Movimiento.tipo_movimiento,
        Movimiento.cantidad,
        case(
            (Movimiento.tipo_movimiento == 'ENTRADA', 'Compra de producto con Factura ' + Movimiento.descripcion),
            (Movimiento.tipo_movimiento == 'VENTA', 'Venta con Factura ' + Movimiento.descripcion),
            (Movimiento.tipo_movimiento == 'TRASLADO', 'Traslado entre bodegas: de ' + Movimiento.bodega_origen_id + ' a ' + Movimiento.bodega_destino_id),
            else_=''
        ).label('descripcion')
    ).filter(Movimiento.producto_id == producto_id).order_by(Movimiento.fecha).all()

    saldo = 0
    kardex = []

    for movimiento in movimientos:
        if movimiento.tipo_movimiento == 'ENTRADA':
            saldo += movimiento.cantidad
        elif movimiento.tipo_movimiento == 'VENTA':
            saldo -= movimiento.cantidad

        kardex.append({
            'fecha': movimiento.fecha.strftime('%Y-%m-%d %H:%M:%S'),
            'tipo': movimiento.tipo_movimiento,
            'cantidad': movimiento.cantidad,
            'saldo': saldo if movimiento.tipo_movimiento != 'TRASLADO' else None,
            'descripcion': movimiento.descripcion
        })

    return kardex

def recalcular_peso_producto_compuesto(producto_id):
    producto = Producto.query.get(producto_id)

    if not producto or not producto.es_producto_compuesto:
        return

    # Sumar el peso de los materiales que lo componen
    materiales = MaterialProducto.query.filter_by(producto_compuesto_id=producto_id).all()
    peso_total = sum(m.cantidad * m.peso_unitario for m in materiales)

    # ✔ Corregimos: el peso total y el peso por unidad deben ser iguales
    producto.peso_total_gr = peso_total
    producto.peso_unidad_gr = peso_total  # 🟢 Aseguramos que sea igual al total

    db.session.commit()


# Función auxiliar para texto envuelto (sin cambios)
def draw_wrapped_text_ajuste(pdf, x, y, text, max_width):
    lines = []
    current_line = ""
    words = text.split()
    font_size = 8  # Coincide con el tamaño ajustado
    pdf.setFont("Helvetica", font_size)

    for word in words:
        test_line = f"{current_line} {word}".strip()
        if pdf.stringWidth(test_line, "Helvetica", font_size) <= max_width:
            current_line = test_line
        else:
            lines.append(current_line)
            current_line = word
    if current_line:
        lines.append(current_line)

    for i, line in enumerate(lines):
        pdf.drawString(x, y - i * (font_size + 2), line)
    return y - (len(lines) - 1) * (font_size + 2)


def draw_wrapped_text_traslado(pdf, x, y, text, max_width):
    """Dibuja texto que salta de línea si excede el ancho máximo y devuelve la altura total usada."""
    words = text.split(" ")
    line = ""
    lines = []
    for word in words:
        test_line = f"{line} {word}".strip()
        if pdf.stringWidth(test_line, "Helvetica", 10) <= max_width:
            line = test_line
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)
    
    y_inicial = y
    for i, line in enumerate(lines):
        pdf.drawString(x, y - (i * 15), line)
    return y - (len(lines) * 15)


# Serializador personalizado para Decimal
def custom_json_serializer(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def create_app():
    app = Flask(__name__, static_folder='static/dist', static_url_path='')
    app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URI
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # Configurar el serializador JSON personalizado
    class CustomJSONEncoder(json.JSONEncoder):
        def default(self, obj):
            if isinstance(obj, Decimal):
                return float(obj)
            return super().default(obj)

    # Usar app.json.encoder para Flask moderno
    app.json_encoder = CustomJSONEncoder  # Para compatibilidad con versiones antiguas
    app.config['JSON_ENCODER'] = CustomJSONEncoder  # Configuración estándar
    from flask.json.provider import DefaultJSONProvider
    class CustomJSONProvider(DefaultJSONProvider):
        def default(self, obj):
            if isinstance(obj, Decimal):
                return float(obj)
            return super().default(obj)
    app.json = CustomJSONProvider(app)  # Reemplazar el proveedor JSON por completo

    db.init_app(app)
    CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)

    with app.app_context():
        try:
            db.session.execute(text("SELECT 1"))
            logger.info("Database connection successful")
        except Exception as e:
            logger.error(f"Database connection failed: {str(e)}")


    # Rutas API (prioridad alta)
    
    #ENDPOINTS LOGIN
    @app.route('/api/login', methods=['POST'])
    def login():
        try:
            data = request.get_json()
            logger.debug(f"Received data: {data}")
            # 📌 Validar datos de entrada
            if not data.get('usuario') or not data.get('password'):
                logger.debug("Missing usuario or password")
                return jsonify({'message': 'Faltan datos para el inicio de sesión'}), 400
                    
            # 🔍 Buscar usuario en la BD
            usuario = Usuario.query.filter_by(usuario=data['usuario']).first()
            logger.debug(f"Found user: {usuario.usuario if usuario else 'None'}")
            if not usuario or not check_password_hash(usuario.password, data['password']):
                logger.debug(f"Password match for {data['usuario']}: {check_password_hash(usuario.password, data['password']) if usuario else 'No user'}")
                return jsonify({'message': 'Credenciales incorrectas'}), 401

            # 🚫 Validar si el usuario está activo
            if not usuario.activo:
                logger.debug(f"User {data['usuario']} is inactive")
                return jsonify({'message': 'Este usuario está inactivo. Contacta al administrador.'}), 409

            # Eliminar sesiones activas existentes del usuario
            sesiones_existentes = SesionActiva.query.filter_by(usuario_id=usuario.id).all()
            message = 'Inicio de sesión exitoso'  # Mensaje por defecto
            if sesiones_existentes:
                for sesion in sesiones_existentes:
                    db.session.delete(sesion)
                db.session.commit()
                logger.debug(f"{len(sesiones_existentes)} sesiones antiguas eliminadas para el usuario {usuario.usuario}")
                message = 'Inicio de sesión exitoso. Se cerró una sesión previa en otro dispositivo.'  # Mensaje actualizado
            else:
                logger.debug(f"No había sesiones activas previas para el usuario {usuario.usuario}")

            # 🔥 Validar si ya se alcanzó el límite global de sesiones activas
            sesiones_activas_totales = SesionActiva.query.count()
            logger.debug(f"Total active sessions: {sesiones_activas_totales}")
            if sesiones_activas_totales >= MAX_SESIONES_CONCURRENTES:
                logger.debug(f"Max sessions reached: {MAX_SESIONES_CONCURRENTES}")
                return jsonify({'message': f'Se ha alcanzado el número máximo de sesiones activas permitidas ({MAX_SESIONES_CONCURRENTES}). Intenta más tarde.'}), 403

            # 🔑 Generar token y crear nueva sesión activa
            token = generate_token()
            
            nueva_sesion = SesionActiva(
                usuario_id=usuario.id,
                token=token,
                ultima_actividad=obtener_hora_colombia(),
                fecha_expiracion=obtener_hora_colombia() + timedelta(hours=2)  # ⏳ Expira en 2 horas
            )
            db.session.add(nueva_sesion)
            db.session.commit()
            logger.debug(f"Nueva sesión creada para {usuario.usuario}. Expiración: {nueva_sesion.fecha_expiracion}")

            # ✅ Respuesta exitosa
            return jsonify({
                'id': usuario.id,
                'usuario': usuario.usuario,
                'nombres': usuario.nombres,
                'apellidos': usuario.apellidos,
                'tipo_usuario': usuario.tipo_usuario,
                'token': token,
                'message': message  # Usar el mensaje dinámico
            }), 200

        except Exception as e:
            logger.error(f"Error en login: {str(e)}")
            db.session.rollback()
            return jsonify({'error': f'Error al iniciar sesión: {str(e)}'}), 500


    @app.before_request
    def verificar_sesion_activa():
        if request.method == 'OPTIONS':
            return '', 200  # Respuesta exitosa a las solicitudes preflight

        if request.endpoint in ['login', 'logout', 'serve_frontend', 'serve_static', 'debug_static']:
            return  # Permitir acceso a rutas públicas sin verificar el token
        if request.path.startswith('/assets/'):  # Permitir acceso a archivos en /assets/
            return
        if request.path.startswith('/images/'):  # Permitir acceso a archivos en /images/
            return
        if request.path.startswith('/static/') or request.path == '/favicon.ico':
            return
        # Verificación de token para rutas protegidas
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        #print(f"DEBUG: Token recibido: {token}")

        if not token:
            print(f"DEBUG: Token no proporcionado para la ruta: {request.path}")
            return jsonify({'message': 'No autorizado. Debes iniciar sesión.'}), 401

        # Buscar la sesión activa en la base de datos
        sesion = SesionActiva.query.filter_by(token=token).first()
        if not sesion:
            print(f"DEBUG: Sesión no encontrada o expirada para el token: {token}")
            return jsonify({'message': 'Sesión no encontrada o expirada.'}), 401

        # Validar tiempo de expiración
        tiempo_actual = obtener_hora_colombia()  # Hora local de Colombia, offset-naive
        #print(f"DEBUG: Tiempo actual: {tiempo_actual}, Expiración: {sesion.fecha_expiracion}")

        # Comparar directamente, ambos son offset-naive
        if sesion.fecha_expiracion < tiempo_actual:
            print("DEBUG: Sesión expirada. Eliminando sesión.")
            db.session.delete(sesion)
            db.session.commit()
            return jsonify({'message': 'Sesión expirada. Por favor, inicia sesión nuevamente.'}), 401

        # Actualizar última actividad y extender la sesión
        sesion.ultima_actividad = obtener_hora_colombia()
        sesion.fecha_expiracion = obtener_hora_colombia() + timedelta(hours=2)  # Extiende la sesión 2 horas
        #print(f"DEBUG: Última actividad actualizada. Nueva expiración: {sesion.fecha_expiracion}")
        db.session.commit()




    @app.route('/api/logout', methods=['POST'])
    def logout():
        try:
            token = request.headers.get('Authorization').replace('Bearer ', '')
            if not token:
                return jsonify({"message": "Token no proporcionado"}), 400

            sesion = SesionActiva.query.filter_by(token=token).first()
            if not sesion:
                return jsonify({"message": "Sesión no encontrada"}), 404

            db.session.delete(sesion)
            db.session.commit()
            return jsonify({"message": "Sesión cerrada correctamente"}), 200
        except Exception as e:
            print(f"Error al cerrar sesión: {str(e)}")
            return jsonify({"error": "Error al cerrar sesión"}), 500


    @app.route('/api/productos', methods=['GET', 'POST'])
    def gestionar_productos():
        if request.method == 'POST':
            data = request.get_json()
            nuevo_producto = Producto(
                codigo=data['codigo'],
                nombre=data['nombre'],
                peso_total_gr=data['peso_total_gr'],
                peso_unidad_gr=data['peso_unidad_gr'],
                codigo_barras=data['codigo_barras'],
                es_producto_compuesto=data['es_producto_compuesto'],
                stock_minimo=data.get('stock_minimo', None)
            )
            db.session.add(nuevo_producto)
            db.session.commit()
            return jsonify({'message': 'Producto creado correctamente'}), 201

        offset = int(request.args.get('offset', 0))
        limit = int(request.args.get('limit', 50))
        search_codigo = request.args.get('search_codigo', '')
        search_nombre = request.args.get('search_nombre', '')
        producto_base_ids = request.args.get('producto_base_ids', '')

        query = Producto.query

        if search_codigo:
            query = query.filter(Producto.codigo.ilike(f'%{search_codigo}%'))
        if search_nombre:
            query = query.filter(Producto.nombre.ilike(f'%{search_nombre}%'))
        if producto_base_ids:
            ids = [int(id) for id in producto_base_ids.split(',') if id.isdigit()]
            if ids:
                query = query.filter(Producto.id.in_(ids))

        total = query.count()

        if limit == 0:
            productos = query.order_by(Producto.codigo.asc()).all()
        else:
            productos = query.order_by(Producto.codigo.asc()).offset(offset).limit(limit).all()

        return jsonify({
            'productos': [{
                'id': p.id,
                'codigo': p.codigo,
                'nombre': p.nombre,
                'peso_total_gr': float(p.peso_total_gr) if p.peso_total_gr is not None else None,
                'peso_unidad_gr': float(p.peso_unidad_gr) if p.peso_unidad_gr is not None else None,
                'codigo_barras': p.codigo_barras,
                'es_producto_compuesto': p.es_producto_compuesto,
                'stock_minimo': p.stock_minimo
            } for p in productos],
            'total': total
        }), 200


        
    @app.route('/api/gestion-productos-materiales', methods=['GET', 'POST'])
    def gestionar_productos_materiales():
        if request.method == 'POST':
            data = request.get_json()

            # Verificar si ya existe un producto con el mismo código o nombre
            producto_existente = Producto.query.filter(
                (Producto.codigo == data['codigo']) | (Producto.nombre.ilike(data['nombre']))
            ).first()

            if producto_existente:
                if producto_existente.codigo == data['codigo']:
                    return jsonify({'error': 'Ya existe un producto con este código. Use otro código.'}), 400
                if producto_existente.nombre.lower() == data['nombre'].lower():
                    return jsonify({'error': 'Ya existe un producto con este nombre. Use otro nombre.'}), 400

            # Crear producto compuesto sin peso (se calculará más adelante)
            if data['es_producto_compuesto']:
                nuevo_producto = Producto(
                    codigo=data['codigo'],
                    nombre=data['nombre'],
                    es_producto_compuesto=True,
                    peso_total_gr=0,  # Se recalculará al agregar materiales
                    peso_unidad_gr=0,  # Se recalculará al agregar materiales
                    codigo_barras=data.get('codigo_barras', None),
                    stock_minimo=data.get('stock_minimo', None)  # Nuevo campo opcional
                )
            else:
                nuevo_producto = Producto(
                    codigo=data['codigo'],
                    nombre=data['nombre'],
                    es_producto_compuesto=False,
                    peso_total_gr=data['peso_total_gr'],
                    peso_unidad_gr=data['peso_unidad_gr'],
                    codigo_barras=data.get('codigo_barras', None),
                    stock_minimo=data.get('stock_minimo', None)  # Nuevo campo opcional
                )

            db.session.add(nuevo_producto)
            db.session.commit()

            return jsonify({'message': 'Producto creado correctamente', 'id': nuevo_producto.id}), 201

        # 🔹 Lógica para manejar GET (Consulta de productos)
        elif request.method == 'GET':
            # Parámetros de consulta para paginación
            offset = int(request.args.get('offset', 0))  # Desplazamiento (inicio)
            limit = int(request.args.get('limit', 20))  # Cantidad máxima de resultados
            search = request.args.get('search', '')

            # Construir la consulta base
            query = Producto.query

            if search:
                query = query.filter(Producto.codigo.ilike(f'%{search}%'))

            # Total de productos (sin paginación) para saber el total
            total = query.count()

            # Aplicar paginación a la consulta
            productos = query.order_by(Producto.codigo.asc()).offset(offset).limit(limit).all()

            if total == 0:
                return jsonify({'error': 'Código de Producto no encontrado. Intente con otro código.'}), 404

            # Devolver los resultados paginados junto con el total
            return jsonify({
                'productos': [{
                    'id': p.id,
                    'codigo': p.codigo,
                    'nombre': p.nombre,
                    'peso_total_gr': p.peso_total_gr,
                    'peso_unidad_gr': p.peso_unidad_gr,
                    'codigo_barras': p.codigo_barras,
                    'es_producto_compuesto': p.es_producto_compuesto,
                    'stock_minimo': p.stock_minimo  # Nuevo campo en la respuesta
                } for p in productos],
                'total': total
            })

    @app.route('/api/materiales-producto', methods=['POST'])
    def agregar_material_a_producto_compuesto():
        try:
            data = request.get_json()
            producto_compuesto_id = data.get('producto_compuesto_id')

            if not producto_compuesto_id:
                return jsonify({'error': 'El ID del producto compuesto es obligatorio.'}), 400

            # Eliminar los materiales actuales del producto compuesto
            MaterialProducto.query.filter_by(producto_compuesto_id=producto_compuesto_id).delete()

            # Agregar los nuevos materiales
            for material in data['materiales']:
                # Convertir cantidad a float, manejar errores si no es numérico
                try:
                    cantidad = float(material['cantidad'])
                except (ValueError, TypeError):
                    return jsonify({'error': f'La cantidad debe ser un número válido para el producto base ID {material["producto_base_id"]}'}), 400

                if cantidad <= 0:
                    return jsonify({'error': f'La cantidad debe ser mayor a 0 para el producto base ID {material["producto_base_id"]}'}), 400
                
                producto_base = db.session.get(Producto, material['producto_base_id'])

                if not producto_base:
                    return jsonify({'error': f'Producto base con ID {material["producto_base_id"]} no encontrado'}), 400

                # Determinar el peso unitario correctamente
                if producto_base.es_producto_compuesto:
                    peso_unitario = producto_base.peso_total_gr  or 0 # ✔️ Para productos compuestos
                else:
                    peso_unitario = producto_base.peso_unidad_gr or 0 # ✔️ Para productos a granel

                # Crear la relación en la tabla materiales_producto
                nuevo_material = MaterialProducto(
                    producto_compuesto_id=producto_compuesto_id,
                    producto_base_id=material['producto_base_id'],
                    cantidad=cantidad,  # Usar el valor convertido
                    peso_unitario=peso_unitario
                )
                db.session.add(nuevo_material)

            db.session.commit()

            # Recalcular el peso del producto compuesto
            recalcular_peso_producto_compuesto(producto_compuesto_id)

            return jsonify({'message': 'Materiales actualizados correctamente'}), 201
        except Exception as e:
            print(f"Error al agregar material: {str(e)} - Data recibida: {data}")
            db.session.rollback()
            return jsonify({'error': f'Error al agregar material: {str(e)}'}), 500



    # Enpoint relativo al cargue de productos de forma masiva por archivo CSV
    @app.route('/api/productos/csv', methods=['POST'])
    def cargar_productos_csv():
        if 'file' not in request.files:
            return jsonify({'error': 'No se ha proporcionado un archivo'}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'Archivo no seleccionado'}), 400

        try:
            stream = TextIOWrapper(file.stream, encoding='utf-8')
            reader = csv.DictReader(stream)
            productos_data = list(reader)

            # Cargar productos existentes
            productos_existentes = Producto.query.with_entities(Producto.codigo, Producto.nombre).all()
            codigos_existentes = {p.codigo for p in productos_existentes}
            nombres_existentes = {p.nombre for p in productos_existentes}

            # Cargar productos base
            codigos_base = set()
            for row in productos_data:
                if row['es_producto_compuesto'].strip().lower() == "si":
                    for i in range(1, int(row.get('cantidad_productos', 0)) + 1):
                        codigo_base = row.get(f'codigo{i}', '').strip()
                        if codigo_base:
                            codigos_base.add(codigo_base)
            productos_base = Producto.query.filter(Producto.codigo.in_(codigos_base)).all()
            productos_base_dict = {p.codigo: (p.id, p.peso_unidad_gr) for p in productos_base}

            productos = []
            materiales = []
            productos_creados = []
            productos_duplicados = []
            errores = []
            batch_size = 100
            productos_compuestos = []

            for row in productos_data:
                codigo = row['codigo'].strip()
                nombre = row['nombre'].strip()
                es_producto_compuesto = row['es_producto_compuesto'].strip().lower() == "si"
                cantidad_productos = int(row['cantidad_productos']) if row.get('cantidad_productos', '') else 0
                stock_minimo = row.get('stock_minimo', '').strip()
                try:
                    stock_minimo = int(float(stock_minimo)) if stock_minimo else None
                except ValueError:
                    errores.append(f"⚠️ ERROR en código {codigo}: El campo 'stock_minimo' debe ser un número entero o estar vacío.")
                    continue

                # Validar duplicados
                if codigo in codigos_existentes:
                    productos_duplicados.append(codigo)
                    continue
                if nombre in nombres_existentes:
                    productos_duplicados.append(codigo)
                    continue

                if not codigo or not nombre:
                    errores.append(f"⚠️ ERROR en código {codigo}: Los campos 'codigo' y 'nombre' son obligatorios.")
                    continue

                if es_producto_compuesto:
                    if row.get('peso_total_gr', '').strip() or row.get('peso_unidad_gr', '').strip():
                        errores.append(f"⚠️ ERROR en código {codigo}: No debe incluir peso_total_gr ni peso_unidad_gr.")
                        continue
                    if cantidad_productos < 1:
                        errores.append(f"⚠️ ERROR en código {codigo}: Debe incluir al menos un producto base.")
                        continue

                    materiales_row = []
                    for i in range(1, cantidad_productos + 1):
                        codigo_base = row.get(f'codigo{i}', '').strip()
                        cantidad_base_str = row.get(f'cantidad{i}', '0').strip()
                        try:
                            cantidad_base = float(cantidad_base_str) if cantidad_base_str else 0.0
                        except ValueError:
                            errores.append(f"⚠️ ERROR en código {codigo}: La cantidad en 'cantidad{i}' no es válida.")
                            continue

                        if not codigo_base or cantidad_base <= 0:
                            errores.append(f"⚠️ ERROR en código {codigo}: La información en 'codigo{i}' o 'cantidad{i}' es inválida.")
                            continue

                        producto_base = productos_base_dict.get(codigo_base)
                        if not producto_base:
                            errores.append(f"⚠️ ERROR en código {codigo}: El producto base '{codigo_base}' no existe.")
                            continue

                        materiales_row.append({
                            'producto_base_id': producto_base[0],
                            'cantidad': cantidad_base,
                            'peso_unitario': producto_base[1]
                        })

                    if materiales_row:
                        producto = Producto(
                            codigo=codigo,
                            nombre=nombre,
                            peso_total_gr=0,
                            peso_unidad_gr=0,
                            codigo_barras=row.get('codigo_barras', None),
                            es_producto_compuesto=True,
                            stock_minimo=stock_minimo
                        )
                        productos.append(producto)
                        productos_compuestos.append({'producto': producto, 'materiales': materiales_row, 'codigo': codigo})
                        productos_creados.append(codigo)
                else:
                    if not row.get('peso_total_gr', '').strip() or not row.get('peso_unidad_gr', '').strip():
                        errores.append(f"⚠️ ERROR en código {codigo}: Debe incluir 'peso_total_gr' y 'peso_unidad_gr'.")
                        continue

                    producto = Producto(
                        codigo=codigo,
                        nombre=nombre,
                        peso_total_gr=float(row['peso_total_gr']),
                        peso_unidad_gr=float(row['peso_unidad_gr']),
                        codigo_barras=row.get('codigo_barras', None),
                        es_producto_compuesto=False,
                        stock_minimo=stock_minimo
                    )
                    productos.append(producto)
                    productos_creados.append(codigo)

            # Guardar todos los productos de una vez
            if productos:
                db.session.bulk_save_objects(productos)
                db.session.commit()

                # Obtener los IDs de los productos recién creados
                productos_creados_db = Producto.query.filter(Producto.codigo.in_(productos_creados)).all()
                productos_id_dict = {p.codigo: p.id for p in productos_creados_db}

                # Asignar materiales a productos compuestos
                for comp in productos_compuestos:
                    producto_id = productos_id_dict.get(comp['codigo'])
                    if not producto_id:
                        errores.append(f"⚠️ ERROR en código {comp['codigo']}: No se encontró el producto después de crearlo.")
                        continue
                    for m in comp['materiales']:
                        materiales.append(MaterialProducto(
                            producto_compuesto_id=producto_id,
                            producto_base_id=m['producto_base_id'],
                            cantidad=m['cantidad'],
                            peso_unitario=m['peso_unitario']
                        ))

                if materiales:
                    db.session.bulk_save_objects(materiales)
                    db.session.commit()

            # Calcular pesos en lote para productos compuestos
            producto_ids = [p.id for p in Producto.query.filter(Producto.es_producto_compuesto == True, Producto.codigo.in_(productos_creados)).all()]
            if producto_ids:
                result = db.session.query(
                    MaterialProducto.producto_compuesto_id,
                    func.sum(MaterialProducto.cantidad * MaterialProducto.peso_unitario).label('peso_total')
                ).filter(
                    MaterialProducto.producto_compuesto_id.in_(producto_ids)
                ).group_by(
                    MaterialProducto.producto_compuesto_id
                ).all()
                pesos = {row.producto_compuesto_id: row.peso_total for row in result}
                for producto_id, peso_total in pesos.items():
                    db.session.query(Producto).filter_by(id=producto_id).update({
                        'peso_total_gr': peso_total,
                        'peso_unidad_gr': peso_total
                    })
                db.session.commit()

            return jsonify({
                'message': '✅ Carga de productos completada.',
                'productos_creados': productos_creados,
                'productos_duplicados': productos_duplicados,
                'errores': errores
            }), 201

        except Exception as e:
            db.session.rollback()
            print(f"Error al cargar productos desde CSV: {str(e)}")
            return jsonify({'error': f'Ocurrió un error al cargar productos desde CSV: {str(e)}'}), 500
        

    # Endpoint para Actualizar productos masivamente mediante .CSV
    # Endpoint para Actualizar productos masivamente mediante .CSV
    @app.route('/api/productos/actualizar-csv', methods=['POST'])
    def actualizar_productos_csv():
        if 'file' not in request.files:
            return jsonify({'error': 'No se ha proporcionado un archivo'}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'Archivo no seleccionado'}), 400

        try:
            stream = TextIOWrapper(file.stream, encoding='utf-8')
            reader = csv.DictReader(stream)
            productos_data = list(reader)

            # Cargar productos existentes
            productos_existentes = Producto.query.with_entities(Producto.id, Producto.codigo, Producto.nombre).all()
            codigos_existentes = {p.codigo: p.id for p in productos_existentes}
            nombres_existentes = {p.nombre: p.id for p in productos_existentes}

            # Cargar productos base para validar materiales
            codigos_base = set()
            for row in productos_data:
                if row.get('es_producto_compuesto', '').strip().lower() == "si":
                    cantidad_productos_str = row.get('cantidad_productos', '').strip()
                    if cantidad_productos_str:
                        try:
                            cantidad_productos = int(cantidad_productos_str)
                            for i in range(1, cantidad_productos + 1):
                                codigo_base = row.get(f'codigo{i}', '').strip()
                                if codigo_base:
                                    codigos_base.add(codigo_base)
                        except ValueError:
                            errores.append(f"⚠️ ERROR en código {row.get('codigo', '')}: 'cantidad_productos' debe ser un número entero.")
                            continue
            productos_base = Producto.query.filter(Producto.codigo.in_(codigos_base)).all()
            productos_base_dict = {p.codigo: (p.id, p.peso_unidad_gr) for p in productos_base}

            productos_actualizados = []
            productos_no_encontrados = []
            errores = []
            batch_size = 100
            materiales_actualizados = []

            for row in productos_data:
                codigo = row.get('codigo', '').strip()
                if not codigo:
                    errores.append("⚠️ ERROR: El campo 'codigo' es obligatorio.")
                    continue

                # Verificar si el producto existe
                producto_id = codigos_existentes.get(codigo)
                if not producto_id:
                    productos_no_encontrados.append(codigo)
                    continue

                nombre = row.get('nombre', '').strip()
                es_producto_compuesto = row.get('es_producto_compuesto', '').strip().lower() == "si"
                stock_minimo = row.get('stock_minimo', '').strip()
                codigo_barras = row.get('codigo_barras', '').strip() or None

                # Validar stock_minimo
                try:
                    stock_minimo = int(float(stock_minimo)) if stock_minimo else None
                except ValueError:
                    errores.append(f"⚠️ ERROR en código {codigo}: El campo 'stock_minimo' debe ser un número entero o estar vacío.")
                    continue

                # Validar nombre único (excluyendo el producto actual)
                if nombre and nombre in nombres_existentes and nombres_existentes[nombre] != producto_id:
                    errores.append(f"⚠️ ERROR en código {codigo}: El nombre '{nombre}' ya está en uso por otro producto.")
                    continue

                # Validar campos según tipo de producto
                if es_producto_compuesto:
                    if row.get('peso_total_gr', '').strip() or row.get('peso_unidad_gr', '').strip():
                        errores.append(f"⚠️ ERROR en código {codigo}: Productos compuestos no deben incluir 'peso_total_gr' ni 'peso_unidad_gr'.")
                        continue
                    
                    # Manejar cantidad_productos solo si está presente y no vacío
                    cantidad_productos_str = row.get('cantidad_productos', '').strip()
                    materiales_row = []
                    if cantidad_productos_str:
                        try:
                            cantidad_productos = int(cantidad_productos_str)
                            if cantidad_productos < 1:
                                errores.append(f"⚠️ ERROR en código {codigo}: 'cantidad_productos' debe ser mayor a 0 si se especifica.")
                                continue

                            # Procesar materiales dinámicamente
                            for i in range(1, cantidad_productos + 1):
                                codigo_base = row.get(f'codigo{i}', '').strip()
                                cantidad_base_str = row.get(f'cantidad{i}', '').strip()
                                if not codigo_base or not cantidad_base_str:
                                    errores.append(f"⚠️ ERROR en código {codigo}: 'codigo{i}' y 'cantidad{i}' son obligatorios si se especifica 'cantidad_productos'.")
                                    continue
                                try:
                                    cantidad_base = float(cantidad_base_str)
                                    if cantidad_base <= 0:
                                        errores.append(f"⚠️ ERROR en código {codigo}: La cantidad en 'cantidad{i}' debe ser mayor a 0.")
                                        continue
                                except ValueError:
                                    errores.append(f"⚠️ ERROR en código {codigo}: La cantidad en 'cantidad{i}' no es válida.")
                                    continue

                                producto_base = productos_base_dict.get(codigo_base)
                                if not producto_base:
                                    errores.append(f"⚠️ ERROR en código {codigo}: El producto base '{codigo_base}' no existe.")
                                    continue

                                materiales_row.append({
                                    'producto_base_id': producto_base[0],
                                    'cantidad': cantidad_base,
                                    'peso_unitario': producto_base[1]
                                })
                        except ValueError:
                            errores.append(f"⚠️ ERROR en código {codigo}: 'cantidad_productos' debe ser un número entero.")
                            continue
                    # Si cantidad_productos está vacío, mantenemos los materiales existentes

                else:
                    peso_total_gr = row.get('peso_total_gr', '').strip()
                    peso_unidad_gr = row.get('peso_unidad_gr', '').strip()
                    try:
                        peso_total_gr = float(peso_total_gr) if peso_total_gr else None
                        peso_unidad_gr = float(peso_unidad_gr) if peso_unidad_gr else None
                    except ValueError:
                        errores.append(f"⚠️ ERROR en código {codigo}: 'peso_total_gr' y 'peso_unidad_gr' deben ser números válidos.")
                        continue

                    if peso_total_gr is None or peso_unidad_gr is None:
                        errores.append(f"⚠️ ERROR en código {codigo}: Productos base deben incluir 'peso_total_gr' y 'peso_unidad_gr'.")
                        continue

                # Actualizar producto
                update_data = {
                    'nombre': nombre,
                    'codigo_barras': codigo_barras,
                    'es_producto_compuesto': es_producto_compuesto,
                    'stock_minimo': stock_minimo
                }
                if not es_producto_compuesto:
                    update_data['peso_total_gr'] = peso_total_gr
                    update_data['peso_unidad_gr'] = peso_unidad_gr
                else:
                    update_data['peso_total_gr'] = 0
                    update_data['peso_unidad_gr'] = 0

                db.session.query(Producto).filter_by(id=producto_id).update(update_data)

                # Actualizar materiales para productos compuestos solo si se proporcionaron nuevos materiales
                if es_producto_compuesto and materiales_row:
                    # Eliminar materiales existentes solo si se especificaron nuevos
                    db.session.query(MaterialProducto).filter_by(producto_compuesto_id=producto_id).delete()
                    # Agregar nuevos materiales
                    for material in materiales_row:
                        materiales_actualizados.append(MaterialProducto(
                            producto_compuesto_id=producto_id,
                            producto_base_id=material['producto_base_id'],
                            cantidad=material['cantidad'],
                            peso_unitario=material['peso_unitario']
                        ))

                productos_actualizados.append(codigo)

                if len(productos_actualizados) % batch_size == 0:
                    db.session.commit()
                    if materiales_actualizados:
                        db.session.bulk_save_objects(materiales_actualizados)
                        db.session.commit()
                    materiales_actualizados = []

            # Commit final
            db.session.commit()
            if materiales_actualizados:
                db.session.bulk_save_objects(materiales_actualizados)
                db.session.commit()

            # Calcular pesos para productos compuestos actualizados
            producto_ids = [codigos_existentes[codigo] for codigo in productos_actualizados
                        if Producto.query.get(codigos_existentes[codigo]).es_producto_compuesto]
            if producto_ids:
                result = db.session.query(
                    MaterialProducto.producto_compuesto_id,
                    func.sum(MaterialProducto.cantidad * MaterialProducto.peso_unitario).label('peso_total')
                ).filter(
                    MaterialProducto.producto_compuesto_id.in_(producto_ids)
                ).group_by(
                    MaterialProducto.producto_compuesto_id
                ).all()
                pesos = {row.producto_compuesto_id: row.peso_total for row in result}
                for producto_id, peso_total in pesos.items():
                    db.session.query(Producto).filter_by(id=producto_id).update({
                        'peso_total_gr': peso_total,
                        'peso_unidad_gr': peso_total
                    })
                db.session.commit()

            return jsonify({
                'message': '✅ Actualización de productos completada.',
                'productos_actualizados': productos_actualizados,
                'productos_no_encontrados': productos_no_encontrados,
                'errores': errores
            }), 200

        except Exception as e:
            db.session.rollback()
            print(f"Error al actualizar productos desde CSV: {str(e)}")
            return jsonify({'error': f'Ocurrió un error al actualizar productos desde CSV: {str(e)}'}), 500

    


    @app.route('/api/productos/<int:producto_id>', methods=['PUT'])
    def actualizar_producto(producto_id):
        try:
            # Buscar el producto en la base de datos
            producto = db.session.query(Producto).get(producto_id)

            if not producto:
                return jsonify({'error': 'Producto no encontrado'}), 404

            # Obtener los datos enviados en la solicitud
            data = request.get_json()

            # Actualizar los valores del producto
            producto.codigo = data.get('codigo', producto.codigo)
            producto.nombre = data.get('nombre', producto.nombre)
            producto.peso_total_gr = data.get('peso_total_gr', producto.peso_total_gr)
            producto.peso_unidad_gr = data.get('peso_unidad_gr', producto.peso_unidad_gr)
            producto.codigo_barras = data.get('codigo_barras', producto.codigo_barras)
            producto.es_producto_compuesto = data.get('es_producto_compuesto', producto.es_producto_compuesto)
            producto.stock_minimo = data.get('stock_minimo', producto.stock_minimo)  # Nuevo campo

            # Guardar los cambios en la base de datos
            db.session.commit()

            return jsonify({'message': 'Producto actualizado correctamente'}), 200
        except Exception as e:
            db.session.rollback()
            print(f"Error al actualizar producto: {str(e)}")
            return jsonify({'error': 'Error al actualizar producto'}), 500

    @app.route('/api/productos/<int:producto_id>', methods=['DELETE'])
    def eliminar_producto(producto_id):
        try:
            # Obtener el producto correctamente
            producto = db.session.get(Producto, producto_id)  

            if not producto:
                return jsonify({'message': 'Producto no encontrado'}), 404

            # Eliminar el producto
            db.session.delete(producto)
            db.session.commit()

            return jsonify({'message': 'Producto eliminado correctamente'}), 200

        except Exception as e:
            print(f"Error al eliminar producto: {e}")
            return jsonify({'error': 'Error interno al eliminar el producto'}), 500



    @app.route('/api/bodegas', methods=['GET', 'POST'])
    def gestionar_bodegas():
        if request.method == 'POST':
            data = request.get_json()
            nueva_bodega = Bodega(nombre=data['nombre'])
            db.session.add(nueva_bodega)
            db.session.commit()
            return jsonify({'message': 'Bodega creada correctamente'}), 201

        bodegas = Bodega.query.all()
        return jsonify([{'id': b.id, 'nombre': b.nombre} for b in bodegas])


    @app.route('/api/bodegas/<int:id>', methods=['PUT', 'DELETE'])
    def modificar_bodega(id):
        bodega = Bodega.db.session.get_or_404(id)

        if request.method == 'PUT':
            data = request.get_json()
            bodega.nombre = data['nombre']
            db.session.commit()
            return jsonify({'message': 'Bodega actualizada correctamente'})

        if request.method == 'DELETE':
            db.session.delete(bodega)
            db.session.commit()
            return jsonify({'message': 'Bodega eliminada correctamente'})
    

    @app.route('/api/cargar_cantidades', methods=['POST'])
    def cargar_cantidades():
        logger.info("Solicitud recibida en /api/cargar_cantidades")

        if 'file' not in request.files:
            logger.error("No se encontró el archivo en la solicitud")
            return jsonify({'message': 'No se encontró el archivo en la solicitud'}), 400

        file = request.files['file']
        logger.info(f"Archivo recibido: {file.filename}")

        if file.filename == '':
            logger.error("No se seleccionó ningún archivo")
            return jsonify({'message': 'No se seleccionó ningún archivo'}), 400

        stream = TextIOWrapper(file.stream, encoding='utf-8')
        reader = csv.DictReader(stream)

        expected_columns = ['factura', 'codigo', 'nombre', 'cantidad', 'bodega', 'contenedor', 'fecha_ingreso', 'costo_unitario']
        logger.info(f"Columnas encontradas en el CSV: {reader.fieldnames}")
        missing_columns = [col for col in expected_columns if col not in reader.fieldnames]
        if missing_columns:
            logger.error(f"Faltan las columnas: {', '.join(missing_columns)}")
            return jsonify({'message': f'Faltan las columnas: {", ".join(missing_columns)}'}), 400

        # Preconsultar productos, bodegas, inventarios y facturas existentes
        productos = {p.codigo: p for p in Producto.query.all()}
        bodegas = {b.nombre: b for b in Bodega.query.all()}
        facturas_existentes = {f.factura.lower() for f in InventarioBodega.query.with_entities(InventarioBodega.factura).distinct().all()}
        inventarios_existentes = {(i.producto_id, i.bodega_id, i.factura.lower()): i for i in InventarioBodega.query.all()}
        estados_existentes = {(e.producto_id, e.bodega_id): e for e in EstadoInventario.query.all()}
        ultimo_consecutivo = db.session.query(func.max(RegistroMovimientos.consecutivo)).scalar() or "T00000"
        consecutivo_base = int(ultimo_consecutivo[1:]) + 1

        errores = []
        nuevos_inventarios = []
        nuevos_estados = []
        nuevos_movimientos = []
        nuevos_kardex = []
        filas_procesadas = 0
        max_filas = 10000  # Límite para evitar sobrecarga
        facturas_csv = {}  # Agrupar filas por factura para validar duplicados internos

        # Primera pasada: Validar duplicados dentro del CSV
        stream.seek(0)
        reader = csv.DictReader(stream)
        for index, row in enumerate(reader, start=1):
            factura = row.get('factura', '').strip().lower()
            codigo = row.get('codigo', '').strip()
            bodega = row.get('bodega', '').strip()
            if not factura or not codigo or not bodega:
                continue  # Errores de datos se validarán en la segunda pasada
            key = (factura, codigo, bodega)
            if factura not in facturas_csv:
                facturas_csv[factura] = []
            facturas_csv[factura].append((index, key))

        # Validar duplicados dentro del CSV
        for factura, filas in facturas_csv.items():
            seen = set()
            for index, key in filas:
                if key in seen:
                    errores.append(f"Fila {index}: Combinación duplicada de factura {key[0]} con producto {key[1]} y bodega {key[2]} en el CSV.")
                seen.add(key)

        # Segunda pasada: Procesar las filas
        stream.seek(0)
        reader = csv.DictReader(stream)
        for index, row in enumerate(reader, start=1):
            if filas_procesadas >= max_filas:
                errores.append(f"Se alcanzó el límite de {max_filas} filas. Divida el archivo en partes más pequeñas.")
                break

            try:
                factura = row.get('factura', '').strip()  # Preservar case-sensitivity
                if not factura:
                    errores.append(f"Fila {index}: El número de factura es obligatorio y no puede estar vacío.")
                    continue

                codigo = row.get('codigo', '').strip()
                nombre = row.get('nombre', '').strip()
                cantidad = row.get('cantidad', '').strip()
                bodega = row.get('bodega', '').strip()
                contenedor = row.get('contenedor', '').strip()
                fecha_ingreso = row.get('fecha_ingreso', '').strip()
                costo_unitario = row.get('costo_unitario', '').strip()

                # Validar datos
                if not codigo:
                    errores.append(f"Fila {index}: El código del producto es obligatorio.")
                    continue
                if not cantidad:
                    errores.append(f"Fila {index}: La cantidad es obligatoria.")
                    continue
                try:
                    cantidad = int(cantidad)
                    if cantidad <= 0:
                        errores.append(f"Fila {index}: La cantidad debe ser mayor que cero.")
                        continue
                except ValueError:
                    errores.append(f"Fila {index}: La cantidad debe ser un número entero.")
                    continue
                if not bodega:
                    errores.append(f"Fila {index}: La bodega es obligatoria.")
                    continue
                try:
                    costo_unitario = float(costo_unitario) if costo_unitario else 0.0
                except ValueError:
                    errores.append(f"Fila {index}: El costo unitario debe ser un número.")
                    continue
                if fecha_ingreso:
                    try:
                        fecha_ingreso = datetime.strptime(fecha_ingreso, '%Y-%m-%d %H:%M:%S')
                    except ValueError:
                        errores.append(f"Fila {index}: Formato de fecha inválido. Use 'YYYY-MM-DD HH:MM:SS'.")
                        continue
                else:
                    fecha_ingreso = obtener_hora_colombia()

                # Validar producto y bodega
                producto = productos.get(codigo)
                if not producto:
                    errores.append(f"Fila {index}: Producto con código {codigo} no encontrado.")
                    continue
                bodega_obj = bodegas.get(bodega)
                if not bodega_obj:
                    errores.append(f"Fila {index}: Bodega con nombre {bodega} no encontrada.")
                    continue

                # Validar factura duplicada en la base de datos
                if (producto.id, bodega_obj.id, factura.lower()) in inventarios_existentes:
                    errores.append(f"Fila {index}: Ya existe un registro con factura {factura} para el producto {codigo} en la bodega {bodega}.")
                    continue

                # Determinar descripción
                descripcion = f"Ingreso de mercancía con Factura de compra {factura}"

                # Preparar inventario_bodega
                inventario = InventarioBodega(
                    producto_id=producto.id,
                    bodega_id=bodega_obj.id,
                    cantidad=cantidad,
                    factura=factura,
                    contenedor=contenedor,
                    fecha_ingreso=fecha_ingreso,
                    costo_unitario=costo_unitario,
                    costo_total=cantidad * costo_unitario
                )
                nuevos_inventarios.append(inventario)
                inventarios_existentes[(producto.id, bodega_obj.id, factura.lower())] = inventario

                # Preparar estado_inventario
                estado_inventario = estados_existentes.get((producto.id, bodega_obj.id))
                if not estado_inventario:
                    estado_inventario = EstadoInventario(
                        producto_id=producto.id,
                        bodega_id=bodega_obj.id,
                        cantidad=cantidad,
                        ultima_actualizacion=fecha_ingreso,
                        costo_unitario=costo_unitario,
                        costo_total=cantidad * costo_unitario
                    )
                    nuevos_estados.append(estado_inventario)
                    estados_existentes[(producto.id, bodega_obj.id)] = estado_inventario
                else:
                    costo_total_nuevo = (float(estado_inventario.cantidad) * float(estado_inventario.costo_unitario)) + (cantidad * costo_unitario)
                    estado_inventario.cantidad += cantidad
                    estado_inventario.costo_unitario = costo_total_nuevo / estado_inventario.cantidad if estado_inventario.cantidad > 0 else costo_unitario
                    estado_inventario.costo_total = estado_inventario.cantidad * estado_inventario.costo_unitario
                    estado_inventario.ultima_actualizacion = fecha_ingreso

                # Generar consecutivo
                nuevo_consecutivo = f"T{consecutivo_base + filas_procesadas:05d}"

                # Preparar registro_movimientos
                nuevo_movimiento = RegistroMovimientos(
                    consecutivo=nuevo_consecutivo,
                    producto_id=producto.id,
                    tipo_movimiento='ENTRADA',
                    cantidad=cantidad,
                    bodega_origen_id=None,
                    bodega_destino_id=bodega_obj.id,
                    fecha=fecha_ingreso,
                    descripcion=descripcion,
                    costo_unitario=costo_unitario,
                    costo_total=cantidad * costo_unitario
                )
                nuevos_movimientos.append(nuevo_movimiento)

                # Preparar kardex
                kardex_entry = Kardex(
                    producto_id=producto.id,
                    bodega_origen_id=None,
                    bodega_destino_id=bodega_obj.id,
                    fecha=fecha_ingreso,
                    tipo_movimiento='ENTRADA',
                    cantidad=cantidad,
                    costo_unitario=costo_unitario,
                    costo_total=cantidad * costo_unitario,
                    saldo_cantidad=estado_inventario.cantidad,
                    saldo_costo_unitario=estado_inventario.costo_unitario,
                    saldo_costo_total=estado_inventario.costo_total,
                    referencia=descripcion
                )
                nuevos_kardex.append(kardex_entry)

                filas_procesadas += 1

            except Exception as e:
                errores.append(f"Fila {index}: Error al procesar la fila ({str(e)})")
                logger.error(f"Fila {index}: Error al procesar - {str(e)}")

        if errores:
            logger.error(f"Errores al procesar el archivo: {errores}")
            db.session.rollback()
            return jsonify({'message': 'Errores al procesar el archivo', 'errors': errores}), 400

        try:
            # Insertar todos los registros en lote
            db.session.bulk_save_objects(nuevos_inventarios)
            db.session.bulk_save_objects(nuevos_estados)
            db.session.bulk_save_objects(nuevos_movimientos)
            db.session.bulk_save_objects(nuevos_kardex)
            db.session.commit()
            logger.info("Cantidades cargadas correctamente")
            return jsonify({'message': 'Cantidades cargadas correctamente'}), 201

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error al guardar en la base de datos: {str(e)}")
            return jsonify({'message': 'Error al guardar los datos', 'errors': [str(e)]}), 500

    @app.route('/api/cargar_notas_credito', methods=['POST'])
    def cargar_notas_credito():
        if 'file' not in request.files:
            return jsonify({'message': 'No se encontró el archivo en la solicitud'}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({'message': 'No se seleccionó ningún archivo'}), 400

        stream = TextIOWrapper(file.stream, encoding='utf-8')
        reader = csv.DictReader(stream)

        # Columnas esperadas: bodega ya no es obligatoria
        expected_columns = ['nota_credito', 'factura', 'codigo', 'nombre', 'cantidad', 'fecha_devolucion']
        optional_columns = ['costo_unitario']
        missing_columns = [col for col in expected_columns if col not in reader.fieldnames]
        if missing_columns:
            return jsonify({'message': f'Faltan las columnas: {", ".join(missing_columns)}'}), 400

        errores = []
        for index, row in enumerate(reader, start=1):
            try:
                nota_credito = row['nota_credito'].strip()
                factura = row['factura'].strip()
                codigo = row['codigo'].strip()
                nombre = row['nombre'].strip()
                cantidad = int(row['cantidad'])
                fecha_devolucion = row.get('fecha_devolucion', None)
                costo_unitario_csv = float(row.get('costo_unitario', 0))  # Costo unitario opcional

                if not nota_credito or not factura:
                    errores.append(f"Fila {index}: 'nota_credito' y 'factura' son obligatorios.")
                    continue

                if fecha_devolucion:
                    fecha_devolucion = datetime.strptime(fecha_devolucion, '%Y-%m-%d %H:%M:%S')
                else:
                    fecha_devolucion = datetime.utcnow()

                producto = Producto.query.filter_by(codigo=codigo).first()
                if not producto:
                    errores.append(f"Fila {index}: Producto con código {codigo} no encontrado.")
                    continue

                # Buscar la salida asociada a la factura en el Kardex
                kardex_salida = Kardex.query.filter(
                    Kardex.producto_id == producto.id,
                    Kardex.tipo_movimiento == 'SALIDA',
                    Kardex.referencia.like(f"%Factura {factura}%")
                ).order_by(Kardex.fecha.desc()).first()

                if not kardex_salida:
                    errores.append(f"Fila {index}: No se encontró una venta con Factura {factura} para el producto {codigo}.")
                    continue

                # Usar la bodega de la salida como destino
                bodega_destino_id = kardex_salida.bodega_origen_id
                bodega_obj = Bodega.query.get(bodega_destino_id)
                if not bodega_obj:
                    errores.append(f"Fila {index}: La bodega de la venta original (ID {bodega_destino_id}) no existe.")
                    continue

                # Usar el costo unitario de la salida si no se proporciona en el CSV
                costo_unitario = costo_unitario_csv if costo_unitario_csv > 0 else kardex_salida.costo_unitario
                costo_total = cantidad * costo_unitario

                # Actualizar o crear registro en inventario_bodega
                inventario = InventarioBodega.query.filter_by(producto_id=producto.id, bodega_id=bodega_obj.id).first()
                if not inventario:
                    inventario = InventarioBodega(
                        producto_id=producto.id,
                        bodega_id=bodega_obj.id,
                        cantidad=cantidad,
                        factura=nota_credito,
                        contenedor=None,
                        fecha_ingreso=fecha_devolucion,
                        costo_unitario=costo_unitario,
                        costo_total=costo_total
                    )
                    db.session.add(inventario)
                    descripcion = f"Devolución inicial por Nota Crédito {nota_credito}"
                else:
                    costo_total_nuevo = (inventario.cantidad * inventario.costo_unitario) + costo_total
                    inventario.cantidad += cantidad
                    inventario.costo_unitario = costo_total_nuevo / inventario.cantidad if inventario.cantidad > 0 else costo_unitario
                    inventario.costo_total = inventario.cantidad * inventario.costo_unitario
                    inventario.fecha_ingreso = fecha_devolucion
                    inventario.factura = nota_credito
                    inventario.contenedor = None
                    descripcion = f"Entrada por devolución con Nota Crédito {nota_credito}"

                # Actualizar o crear registro en estado_inventario
                estado_inventario = EstadoInventario.query.filter_by(
                    producto_id=producto.id, bodega_id=bodega_obj.id
                ).first()
                if not estado_inventario:
                    estado_inventario = EstadoInventario(
                        producto_id=producto.id,
                        bodega_id=bodega_obj.id,
                        cantidad=cantidad,
                        ultima_actualizacion=fecha_devolucion,
                        costo_unitario=costo_unitario,
                        costo_total=costo_total
                    )
                    db.session.add(estado_inventario)
                else:
                    costo_total_nuevo = (estado_inventario.cantidad * estado_inventario.costo_unitario) + costo_total
                    estado_inventario.cantidad += cantidad
                    estado_inventario.costo_unitario = costo_total_nuevo / estado_inventario.cantidad if estado_inventario.cantidad > 0 else costo_unitario
                    estado_inventario.costo_total = estado_inventario.cantidad * estado_inventario.costo_unitario
                    estado_inventario.ultima_actualizacion = fecha_devolucion

                # Generar nuevo consecutivo
                ultimo_consecutivo = db.session.query(
                    db.func.max(db.cast(RegistroMovimientos.consecutivo, db.String))
                ).scalar() or "T00000"
                nuevo_consecutivo = f"T{int(ultimo_consecutivo[1:]) + 1:05d}"

                # Registrar movimiento como ENTRADA en RegistroMovimientos
                nuevo_movimiento = RegistroMovimientos(
                    consecutivo=nuevo_consecutivo,
                    producto_id=producto.id,
                    tipo_movimiento='ENTRADA',
                    cantidad=cantidad,
                    bodega_origen_id=None,
                    bodega_destino_id=bodega_obj.id,
                    fecha=fecha_devolucion,
                    descripcion=descripcion,
                    costo_unitario=costo_unitario,
                    costo_total=costo_total
                )
                db.session.add(nuevo_movimiento)

                # Registrar en Kardex
                kardex_entry = Kardex(
                    producto_id=producto.id,
                    bodega_origen_id=None,
                    bodega_destino_id=bodega_obj.id,
                    fecha=fecha_devolucion,
                    tipo_movimiento='ENTRADA',
                    cantidad=cantidad,
                    costo_unitario=costo_unitario,
                    costo_total=costo_total,
                    saldo_cantidad=estado_inventario.cantidad,
                    saldo_costo_unitario=estado_inventario.costo_unitario,
                    saldo_costo_total=estado_inventario.costo_total,
                    referencia=f"Entrada por devolución con Nota Crédito {nota_credito} (Factura {factura})"
                )
                db.session.add(kardex_entry)

                db.session.commit()

            except Exception as e:
                db.session.rollback()
                errores.append(f"Fila {index}: Error al procesar la fila ({str(e)})")

        if errores:
            return jsonify({'message': 'Errores al procesar el archivo', 'errors': errores}), 400

        return jsonify({'message': 'Notas crédito cargadas correctamente'}), 201
    
    
    
    @app.route('/api/notas_credito', methods=['GET'])
    def listar_notas_credito():
        try:
            notas_credito = db.session.query(InventarioBodega.factura).filter(
                InventarioBodega.factura.like('NC%')
            ).distinct().all()
            notas_credito_lista = [nota[0] for nota in notas_credito if nota[0]]
            return jsonify({'notas_credito': notas_credito_lista})
        except Exception as e:
            print(f"Error al listar notas crédito: {str(e)}")
            return jsonify({'error': 'Error al listar notas crédito'}), 500


    @app.route('/api/detalle_nota_credito', methods=['GET'])
    def detalle_nota_credito():
        try:
            nota_credito = request.args.get('nota_credito')
            if not nota_credito:
                return jsonify({'error': 'Se requiere el número de nota crédito'}), 400

            query = db.session.query(
                Producto.codigo,
                Producto.nombre,
                RegistroMovimientos.cantidad,
                Bodega.nombre.label('bodega'),
                RegistroMovimientos.costo_unitario,  # Nuevo
                RegistroMovimientos.costo_total      # Nuevo
            ).join(
                Producto, RegistroMovimientos.producto_id == Producto.id
            ).join(
                Bodega, RegistroMovimientos.bodega_destino_id == Bodega.id
            ).join(
                InventarioBodega,
                (RegistroMovimientos.producto_id == InventarioBodega.producto_id) &
                (RegistroMovimientos.bodega_destino_id == InventarioBodega.bodega_id)
            ).filter(
                RegistroMovimientos.tipo_movimiento == 'ENTRADA',
                InventarioBodega.factura == nota_credito
            )

            resultados = query.all()

            if not resultados:
                return jsonify([])

            response = [
                {
                    'codigo': item.codigo,
                    'nombre': item.nombre,
                    'cantidad': float(item.cantidad),
                    'bodega': item.bodega,
                    'costo_unitario': float(item.costo_unitario) if item.costo_unitario is not None else 0.0,
                    'costo_total': float(item.costo_total) if item.costo_total is not None else 0.0
                }
                for item in resultados
            ]
            return jsonify(response)
        except Exception as e:
            print(f"Error al obtener detalle de nota crédito: {str(e)}")
            return jsonify({'error': 'Error al obtener detalle de nota crédito'}), 500
    

    @app.route('/api/consultar_notas_credito', methods=['GET'])
    def consultar_notas_credito():
        try:
            nota_credito = request.args.get('nota_credito')
            fecha_inicio = request.args.get('fecha_inicio')
            fecha_fin = request.args.get('fecha_fin')

            query = db.session.query(
                InventarioBodega.factura.label('nota_credito'),
                db.func.min(RegistroMovimientos.fecha).label('fecha')
            ).join(
                RegistroMovimientos,
                (RegistroMovimientos.producto_id == InventarioBodega.producto_id) &
                (RegistroMovimientos.bodega_destino_id == InventarioBodega.bodega_id)
            ).filter(
                RegistroMovimientos.tipo_movimiento == 'ENTRADA',
                InventarioBodega.factura.like('NC%')
            )

            if nota_credito:
                query = query.filter(InventarioBodega.factura == nota_credito)
            if fecha_inicio:
                query = query.filter(RegistroMovimientos.fecha >= fecha_inicio)
            if fecha_fin:
                query = query.filter(RegistroMovimientos.fecha <= fecha_fin)

            query = query.group_by(InventarioBodega.factura)
            resultados = query.order_by(db.func.min(RegistroMovimientos.fecha)).all()

            if not resultados:
                return jsonify([])

            response = [
                {
                    'nota_credito': item.nota_credito,
                    'fecha': item.fecha.strftime('%Y-%m-%d %H:%M:%S')
                }
                for item in resultados
            ]
            return jsonify(response)
        except Exception as e:
            print(f"Error al consultar notas crédito: {str(e)}")
            return jsonify({'error': 'Error al consultar notas crédito'}), 500


    @app.route('/api/facturas', methods=['GET'])
    def listar_facturas():
        try:
            facturas = db.session.query(InventarioBodega.factura).distinct().all()
            facturas_lista = [factura[0] for factura in facturas if factura[0]]
            return jsonify({'facturas': facturas_lista})
        except Exception as e:
            print(f"Error al listar facturas: {str(e)}")
            return jsonify({'error': 'Error al listar facturas'}), 500




    @app.route('/api/consultar_facturas', methods=['GET'])
    def consultar_facturas():
        try:
            factura = request.args.get('factura')
            fecha_inicio = request.args.get('fecha_inicio')
            fecha_fin = request.args.get('fecha_fin')

            query = db.session.query(
                InventarioBodega.factura,
                db.func.min(InventarioBodega.fecha_ingreso).label('fecha')
            ).filter(
                InventarioBodega.factura.isnot(None)
            )

            if factura:
                query = query.filter(InventarioBodega.factura.ilike(f'%{factura}%'))
            if fecha_inicio:
                query = query.filter(InventarioBodega.fecha_ingreso >= fecha_inicio)
            if fecha_fin:
                query = query.filter(InventarioBodega.fecha_ingreso <= fecha_fin)

            resultados = query.group_by(InventarioBodega.factura).order_by(db.func.min(InventarioBodega.fecha_ingreso)).all()

            if not resultados:
                return jsonify([])

            response = []
            seen_facturas = set()
            for item in resultados:
                factura_num = item.factura.strip()
                if factura_num.startswith('NC') or factura_num in seen_facturas:
                    continue

                seen_facturas.add(factura_num)
                response.append({
                    'factura': factura_num,
                    'fecha': item.fecha.strftime('%Y-%m-%d %H:%M:%S')
                })

            return jsonify(response)
        except Exception as e:
            print(f"Error al consultar facturas: {str(e)}")
            return jsonify({'error': 'Error al consultar facturas'}), 500



    @app.route('/api/detalle_factura', methods=['GET'])
    def detalle_factura():
        try:
            factura = request.args.get('factura')
            if not factura:
                return jsonify({'error': 'Se requiere el número de factura'}), 400

            # Limpiar factura si contiene prefijo
            factura_clean = factura.replace('factura de compra ', '').strip()

            query = db.session.query(
                Producto.codigo,
                Producto.nombre,
                RegistroMovimientos.cantidad,
                Bodega.nombre.label('bodega'),
                RegistroMovimientos.costo_unitario,
                RegistroMovimientos.costo_total
            ).join(
                Producto, RegistroMovimientos.producto_id == Producto.id
            ).join(
                Bodega, RegistroMovimientos.bodega_destino_id == Bodega.id
            ).join(
                InventarioBodega,
                (RegistroMovimientos.producto_id == InventarioBodega.producto_id) &
                (RegistroMovimientos.bodega_destino_id == InventarioBodega.bodega_id) &
                (db.func.date(RegistroMovimientos.fecha) == db.func.date(InventarioBodega.fecha_ingreso))
            ).filter(
                RegistroMovimientos.tipo_movimiento == 'ENTRADA',
                InventarioBodega.factura == factura_clean
            ).order_by(
                Producto.codigo,
                Bodega.nombre,
                RegistroMovimientos.fecha.desc()
            ).distinct(Producto.codigo, Bodega.nombre)

            resultados = query.all()

            if not resultados:
                return jsonify([])

            response = [
                {
                    'id': f"{item.codigo}_{item.bodega}",
                    'codigo': item.codigo,
                    'nombre': item.nombre,
                    'cantidad': float(item.cantidad),
                    'bodega': item.bodega,
                    'costo_unitario': float(item.costo_unitario) if item.costo_unitario is not None else 0.0,
                    'costo_total': float(item.costo_total) if item.costo_total is not None else 0.0
                }
                for item in resultados
            ]
            return jsonify(response)
        except Exception as e:
            print(f"Error al obtener detalle de factura: {str(e)}")
            return jsonify({'error': f'Error al obtener detalle de factura: {str(e)}'}), 500
    

    @app.route('/api/inventario/<string:codigo_producto>', methods=['GET'])
    def consultar_inventario_por_producto(codigo_producto):
        try:
            # Obtener el producto por código
            producto = Producto.query.filter_by(codigo=codigo_producto).first()
            if not producto:
                return jsonify({'message': f'Producto con código {codigo_producto} no encontrado'}), 404

            # Obtener el inventario consolidado
            inventario = calcular_inventario_producto(producto.id)
            if not inventario:
                return jsonify({'message': f'No hay inventario registrado para el producto {codigo_producto}.'}), 200

            # Respuesta estructurada
            return jsonify({
                'producto': {
                    'codigo': producto.codigo,
                    'nombre': producto.nombre,
                },
                'inventario': inventario
            })
        except Exception as e:
            print(f"Error al consultar inventario por producto: {str(e)}")
            return jsonify({'error': 'Error al consultar inventario'}), 500


    @app.route('/api/inventario-con-costos/<string:codigo_producto>', methods=['GET'])
    def consultar_inventario_por_producto_con_costos(codigo_producto):
        try:
            producto = Producto.query.filter_by(codigo=codigo_producto).first()
            if not producto:
                return jsonify({'message': f'Producto con código {codigo_producto} no encontrado'}), 404

            inventario = calcular_inventario_producto(producto.id)
            if not inventario:
                return jsonify({'message': f'No hay inventario registrado para el producto {codigo_producto}.'}), 200

            # Obtener costos del Kardex por bodega
            inventario_con_costos = []
            for item in inventario:
                ultimo_kardex = db.session.query(Kardex).filter(
                    Kardex.producto_id == producto.id,
                    Kardex.bodega_destino_id == Bodega.query.filter_by(nombre=item['bodega']).first().id
                ).order_by(Kardex.fecha.desc()).first()
                costo_unitario = ultimo_kardex.saldo_costo_unitario if ultimo_kardex else 0.0
                costo_total = costo_unitario * item['cantidad']
                inventario_con_costos.append({
                    'bodega': item['bodega'],
                    'cantidad': item['cantidad'],
                    'costo_unitario': float(costo_unitario),
                    'costo_total': float(costo_total),
                })

            return jsonify({
                'producto': {
                    'codigo': producto.codigo,
                    'nombre': producto.nombre,
                    'stock_minimo': producto.stock_minimo  # Nuevo campo en la respuesta
                },
                'inventario': inventario_con_costos
            })
        except Exception as e:
            print(f"Error al consultar inventario por producto con costos: {str(e)}")
            return jsonify({'error': 'Error al consultar inventario'}), 500


    # ENPOINTS PARA TRASLADOS BODEGA
    @app.route('/api/traslados', methods=['GET'])
    def consultar_traslados():
        try:
            # Crear alias para las bodegas
            BodegaOrigen = aliased(Bodega)
            BodegaDestino = aliased(Bodega)

            # Obtener parámetros de consulta
            consecutivo = request.args.get('consecutivo')
            codigo_producto = request.args.get('codigo')
            fecha_inicio = request.args.get('fecha_inicio')
            fecha_fin = request.args.get('fecha_fin')

            # Construir consulta base
            query = db.session.query(
                RegistroMovimientos.consecutivo,
                RegistroMovimientos.fecha,
                Producto.nombre.label('producto_nombre'),
                RegistroMovimientos.cantidad,
                BodegaOrigen.nombre.label('bodega_origen'),
                BodegaDestino.nombre.label('bodega_destino'),
                Kardex.costo_unitario,
                Kardex.costo_total
            ).join(
                Producto, RegistroMovimientos.producto_id == Producto.id
            ).join(
                BodegaOrigen, RegistroMovimientos.bodega_origen_id == BodegaOrigen.id
            ).join(
                BodegaDestino, RegistroMovimientos.bodega_destino_id == BodegaDestino.id
            ).join(
                Kardex, (Kardex.referencia == db.func.concat('Traslado ', RegistroMovimientos.consecutivo, ' de ', BodegaOrigen.nombre, ' a ', BodegaDestino.nombre)) &
                        (Kardex.producto_id == RegistroMovimientos.producto_id) &
                        (Kardex.tipo_movimiento == 'SALIDA')
            ).filter(
                RegistroMovimientos.tipo_movimiento == 'TRASLADO'
            )

            # Aplicar filtros si existen
            if consecutivo:
                query = query.filter(RegistroMovimientos.consecutivo == consecutivo)
            if codigo_producto:
                producto = Producto.query.filter_by(codigo=codigo_producto).first()
                if not producto:
                    return jsonify({'error': f'Producto con código {codigo_producto} no encontrado.'}), 404
                query = query.filter(RegistroMovimientos.producto_id == producto.id)
            if fecha_inicio:
                try:
                    datetime.strptime(fecha_inicio, '%Y-%m-%d')
                    query = query.filter(RegistroMovimientos.fecha >= fecha_inicio)
                except ValueError:
                    return jsonify({'error': 'Formato de fecha_inicio inválido. Use YYYY-MM-DD.'}), 400
            if fecha_fin:
                try:
                    datetime.strptime(fecha_fin, '%Y-%m-%d')
                    query = query.filter(RegistroMovimientos.fecha <= fecha_fin)
                except ValueError:
                    return jsonify({'error': 'Formato de fecha_fin inválido. Use YYYY-MM-DD.'}), 400

            # Ejecutar consulta
            traslados = query.order_by(RegistroMovimientos.fecha).all()
            print(f"Total traslados obtenidos: {len(traslados)}")

            # Construir resultado
            resultado = [
                {
                    'consecutivo': traslado.consecutivo,
                    'fecha': traslado.fecha.strftime('%Y-%m-%d %H:%M:%S'),
                    'producto': traslado.producto_nombre,
                    'cantidad': traslado.cantidad,
                    'bodega_origen': traslado.bodega_origen,
                    'bodega_destino': traslado.bodega_destino,
                    'costo_unitario': float(traslado.costo_unitario or 0.0),
                    'costo_total': float(traslado.costo_total or 0.0)
                }
                for traslado in traslados
            ]

            return jsonify(resultado)

        except Exception as e:
            print(f"Error al consultar traslados: {str(e)}")
            return jsonify({'error': 'Error al consultar traslados'}), 500



    @app.route('/api/traslados-por-bodega', methods=['GET'])
    def consultar_traslados_por_bodega():
        try:
            # Crear alias para las bodegas
            BodegaOrigen = aliased(Bodega)
            BodegaDestino = aliased(Bodega)

            # Obtener parámetros de consulta
            consecutivo = request.args.get('consecutivo')
            codigo_producto = request.args.get('codigo')
            fecha_inicio = request.args.get('fecha_inicio')
            fecha_fin = request.args.get('fecha_fin')
            bodega_origen = request.args.get('bodega_origen')
            bodega_destino = request.args.get('bodega_destino')

            # Construir consulta base
            query = db.session.query(
                RegistroMovimientos.consecutivo,
                RegistroMovimientos.fecha,
                Producto.nombre.label('producto_nombre'),
                RegistroMovimientos.cantidad,
                BodegaOrigen.nombre.label('bodega_origen'),
                BodegaDestino.nombre.label('bodega_destino'),
                Kardex.costo_unitario,
                Kardex.costo_total
            ).join(
                Producto, RegistroMovimientos.producto_id == Producto.id
            ).join(
                BodegaOrigen, RegistroMovimientos.bodega_origen_id == BodegaOrigen.id
            ).join(
                BodegaDestino, RegistroMovimientos.bodega_destino_id == BodegaDestino.id
            ).join(
                Kardex, (Kardex.referencia == db.func.concat('Traslado ', RegistroMovimientos.consecutivo, ' de ', BodegaOrigen.nombre, ' a ', BodegaDestino.nombre)) &
                        (Kardex.producto_id == RegistroMovimientos.producto_id) &
                        (Kardex.tipo_movimiento == 'SALIDA')
            ).filter(
                RegistroMovimientos.tipo_movimiento == 'TRASLADO'
            )

            # Aplicar filtros si existen
            if consecutivo:
                query = query.filter(RegistroMovimientos.consecutivo == consecutivo)
            if codigo_producto:
                producto = Producto.query.filter_by(codigo=codigo_producto).first()
                if not producto:
                    return jsonify({'error': f'Producto con código {codigo_producto} no encontrado.'}), 404
                query = query.filter(RegistroMovimientos.producto_id == producto.id)
            if fecha_inicio:
                try:
                    datetime.strptime(fecha_inicio, '%Y-%m-%d')
                    query = query.filter(RegistroMovimientos.fecha >= fecha_inicio)
                except ValueError:
                    return jsonify({'error': 'Formato de fecha_inicio inválido. Use YYYY-MM-DD.'}), 400
            if fecha_fin:
                try:
                    datetime.strptime(fecha_fin, '%Y-%m-%d')
                    query = query.filter(RegistroMovimientos.fecha <= fecha_fin)
                except ValueError:
                    return jsonify({'error': 'Formato de fecha_fin inválido. Use YYYY-MM-DD.'}), 400
            if bodega_origen:
                bodega = Bodega.query.filter_by(nombre=bodega_origen).first()
                if not bodega:
                    return jsonify({'error': f'Bodega de origen {bodega_origen} no encontrada.'}), 404
                query = query.filter(RegistroMovimientos.bodega_origen_id == bodega.id)
            if bodega_destino:
                bodega = Bodega.query.filter_by(nombre=bodega_destino).first()
                if not bodega:
                    return jsonify({'error': f'Bodega de destino {bodega_destino} no encontrada.'}), 404
                query = query.filter(RegistroMovimientos.bodega_destino_id == bodega.id)

            # Ejecutar consulta
            traslados = query.order_by(RegistroMovimientos.fecha).all()
            print(f"Total traslados obtenidos: {len(traslados)}")

            # Construir resultado
            resultado = [
                {
                    'consecutivo': traslado.consecutivo,
                    'fecha': traslado.fecha.strftime('%Y-%m-%d %H:%M:%S'),
                    'producto': traslado.producto_nombre,
                    'cantidad': traslado.cantidad,
                    'bodega_origen': traslado.bodega_origen,
                    'bodega_destino': traslado.bodega_destino,
                    'costo_unitario': float(traslado.costo_unitario or 0.0),
                    'costo_total': float(traslado.costo_total or 0.0)
                }
                for traslado in traslados
            ]

            return jsonify(resultado)

        except Exception as e:
            print(f"Error al consultar traslados por bodega: {str(e)}")
            return jsonify({'error': 'Error al consultar traslados por bodega'}), 500


    @app.route('/api/trasladar_cantidades', methods=['POST'])
    def trasladar_cantidades():
        try:
            data = request.get_json()

            if not data or not all(key in data for key in ('codigo', 'bodega_origen', 'bodega_destino', 'cantidad')):
                return jsonify({'error': 'Datos incompletos'}), 400

            codigo_producto = data['codigo']
            bodega_origen = data['bodega_origen']
            bodega_destino = data['bodega_destino']
            cantidad = data['cantidad']

            if cantidad <= 0:
                return jsonify({'error': 'La cantidad debe ser mayor a cero'}), 400

            producto = Producto.query.filter_by(codigo=codigo_producto).first()
            if not producto:
                return jsonify({'error': 'Producto no encontrado'}), 404

            bodega_origen_obj = Bodega.query.filter_by(nombre=bodega_origen).first()
            bodega_destino_obj = Bodega.query.filter_by(nombre=bodega_destino).first()

            if not bodega_origen_obj or not bodega_destino_obj:
                return jsonify({'error': 'Bodega origen o destino no encontrada'}), 404

            # Calcular inventario disponible en la bodega origen
            entradas_origen = db.session.query(
                db.func.sum(InventarioBodega.cantidad)
            ).filter(
                InventarioBodega.bodega_id == bodega_origen_obj.id,
                InventarioBodega.producto_id == producto.id
            ).scalar() or 0

            salidas_origen = db.session.query(
                db.func.sum(Movimiento.cantidad)
            ).filter(
                Movimiento.bodega_origen_id == bodega_origen_obj.id,
                Movimiento.producto_id == producto.id,
                Movimiento.tipo_movimiento.in_(['TRASLADO', 'VENTA'])
            ).scalar() or 0

            # Incluir traslados entrantes en las entradas
            traslados_entrantes = db.session.query(
                db.func.sum(Movimiento.cantidad)
            ).filter(
                Movimiento.bodega_destino_id == bodega_origen_obj.id,
                Movimiento.producto_id == producto.id,
                Movimiento.tipo_movimiento == 'TRASLADO'
            ).scalar() or 0

            inventario_disponible = entradas_origen + traslados_entrantes - salidas_origen

            print(f"Entradas iniciales: {entradas_origen}, Traslados Entrantes: {traslados_entrantes}, Salidas: {salidas_origen}, Inventario Disponible: {inventario_disponible}")

            if inventario_disponible <= 0:
                return jsonify({'error': f'No hay inventario registrado en {bodega_origen} para este producto.'}), 400

            if inventario_disponible < cantidad:
                return jsonify({'error': 'Cantidad insuficiente en la bodega origen'}), 400

            # Registrar el traslado
            inventario_origen = InventarioBodega.query.filter_by(
                bodega_id=bodega_origen_obj.id, producto_id=producto.id
            ).first()
            if not inventario_origen:
                inventario_origen = InventarioBodega(
                    bodega_id=bodega_origen_obj.id, producto_id=producto.id, cantidad=0
                )
                db.session.add(inventario_origen)

            inventario_origen.cantidad -= cantidad

            inventario_destino = InventarioBodega.query.filter_by(
                bodega_id=bodega_destino_obj.id, producto_id=producto.id
            ).first()
            if not inventario_destino:
                inventario_destino = InventarioBodega(
                    bodega_id=bodega_destino_obj.id, producto_id=producto.id, cantidad=0
                )
                db.session.add(inventario_destino)

            inventario_destino.cantidad += cantidad

            nuevo_movimiento = Movimiento(
                tipo_movimiento='TRASLADO',
                producto_id=producto.id,
                bodega_origen_id=bodega_origen_obj.id,
                bodega_destino_id=bodega_destino_obj.id,
                cantidad=cantidad,
                fecha=obtener_hora_colombia(),
            )
            db.session.add(nuevo_movimiento)

            db.session.commit()
            return jsonify({'message': 'Traslado realizado correctamente'}), 200

        except Exception as e:
            print(f"Error al realizar el traslado: {e}")
            db.session.rollback()
            return jsonify({'error': 'Ocurrió un error al realizar el traslado'}), 500


    @app.route('/api/trasladar_varios', methods=['POST'])
    def trasladar_varios():
        try:
            data = request.get_json()
            productos = data.get('productos', [])
            if not productos:
                return jsonify({'error': 'No se proporcionaron productos para trasladar.'}), 400

            ultimo_consecutivo = db.session.query(
                db.func.max(db.cast(RegistroMovimientos.consecutivo, db.String))
            ).scalar() or "T00000"
            nuevo_consecutivo = f"T{int(ultimo_consecutivo[1:]) + 1:05d}"

            for producto in productos:
                codigo = producto.get('codigo')
                bodega_origen = producto.get('bodega_origen')
                bodega_destino = producto.get('bodega_destino')
                cantidad = producto.get('cantidad')

                if not all([codigo, bodega_origen, bodega_destino, cantidad]):
                    return jsonify({'error': f'Datos incompletos para el producto {codigo}.'}), 400

                producto_obj = Producto.query.filter_by(codigo=codigo).first()
                if not producto_obj:
                    return jsonify({'error': f'Producto con código {codigo} no encontrado.'}), 404

                bodega_origen_obj = Bodega.query.filter_by(nombre=bodega_origen).first()
                bodega_destino_obj = Bodega.query.filter_by(nombre=bodega_destino).first()
                if not bodega_origen_obj or not bodega_destino_obj:
                    return jsonify({'error': f'Bodegas no encontradas: Origen={bodega_origen}, Destino={bodega_destino}.'}), 404

                inventario_origen = EstadoInventario.query.filter_by(
                    bodega_id=bodega_origen_obj.id,
                    producto_id=producto_obj.id
                ).first()
                if not inventario_origen or inventario_origen.cantidad < cantidad:
                    cantidad_disponible = inventario_origen.cantidad if inventario_origen else 0
                    return jsonify({
                        'error': f'Inventario insuficiente en {bodega_origen} para el producto {codigo}. '
                                f'Disponible: {cantidad_disponible}, Requerido: {cantidad}.'
                    }), 400

                # Calcular costo unitario promedio desde Kardex
                movimientos_previos = Kardex.query.filter(
                    Kardex.producto_id == producto_obj.id,
                    Kardex.bodega_destino_id == bodega_origen_obj.id,
                    Kardex.fecha <= obtener_hora_colombia()
                ).order_by(Kardex.fecha.desc()).first()
                costo_unitario = movimientos_previos.saldo_costo_unitario if movimientos_previos else 0.0
                costo_total = cantidad * costo_unitario

                # Calcular saldos actuales
                saldo_origen_previo = inventario_origen.cantidad
                saldo_destino_previo = EstadoInventario.query.filter_by(
                    bodega_id=bodega_destino_obj.id,
                    producto_id=producto_obj.id
                ).first()
                saldo_destino_previo = saldo_destino_previo.cantidad if saldo_destino_previo else 0

                # Actualizar inventario
                inventario_origen.cantidad -= cantidad
                inventario_destino = EstadoInventario.query.filter_by(
                    bodega_id=bodega_destino_obj.id,
                    producto_id=producto_obj.id
                ).first()
                if not inventario_destino:
                    inventario_destino = EstadoInventario(
                        bodega_id=bodega_destino_obj.id,
                        producto_id=producto_obj.id,
                        cantidad=0
                    )
                    db.session.add(inventario_destino)
                inventario_destino.cantidad += cantidad

                # Registrar movimientos en Kardex
                kardex_salida = Kardex(
                    producto_id=producto_obj.id,
                    tipo_movimiento='SALIDA',
                    cantidad=cantidad,
                    bodega_origen_id=bodega_origen_obj.id,
                    costo_unitario=costo_unitario,
                    costo_total=costo_total,
                    saldo_cantidad=saldo_origen_previo - cantidad,  # Saldo después de la salida
                    saldo_costo_unitario=costo_unitario,
                    saldo_costo_total=(saldo_origen_previo - cantidad) * costo_unitario,
                    fecha=obtener_hora_colombia(),
                    referencia=f"Traslado {nuevo_consecutivo} de {bodega_origen} a {bodega_destino}"
                )
                kardex_entrada = Kardex(
                    producto_id=producto_obj.id,
                    tipo_movimiento='ENTRADA',
                    cantidad=cantidad,
                    bodega_destino_id=bodega_destino_obj.id,
                    costo_unitario=costo_unitario,
                    costo_total=costo_total,
                    saldo_cantidad=saldo_destino_previo + cantidad,  # Saldo después de la entrada
                    saldo_costo_unitario=costo_unitario,
                    saldo_costo_total=(saldo_destino_previo + cantidad) * costo_unitario,
                    fecha=obtener_hora_colombia(),
                    referencia=f"Traslado {nuevo_consecutivo} de {bodega_origen} a {bodega_destino}"
                )
                db.session.add(kardex_salida)
                db.session.add(kardex_entrada)

                nuevo_movimiento = RegistroMovimientos(
                    consecutivo=nuevo_consecutivo,
                    tipo_movimiento='TRASLADO',
                    producto_id=producto_obj.id,
                    bodega_origen_id=bodega_origen_obj.id,
                    bodega_destino_id=bodega_destino_obj.id,
                    cantidad=cantidad,
                    fecha=obtener_hora_colombia(),
                    descripcion=f"Traslado de {cantidad} unidades de {codigo} de {bodega_origen} a {bodega_destino}"
                )
                db.session.add(nuevo_movimiento)

            db.session.commit()
            return jsonify({'message': 'Traslado realizado correctamente.', 'consecutivo': nuevo_consecutivo}), 200

        except Exception as e:
            print(f"Error al registrar traslados múltiples: {e}")
            db.session.rollback()
            return jsonify({'error': 'Ocurrió un error al registrar los traslados.'}), 500


    # Imprimir listado de traslados en PDF
    @app.route('/api/traslados-pdf', methods=['GET'])
    def generar_traslados_pdf():
        try:
            # Obtener parámetros de consulta
            consecutivo = request.args.get('consecutivo')
            codigo = request.args.get('codigo')
            fecha_inicio = request.args.get('fecha_inicio')
            fecha_fin = request.args.get('fecha_fin')
            bodega_origen = request.args.get('bodega_origen')  # Nuevo parámetro
            bodega_destino = request.args.get('bodega_destino')  # Nuevo parámetro

            # Construir consulta base
            query = RegistroMovimientos.query.filter_by(tipo_movimiento='TRASLADO')

            # Aplicar filtros si existen
            if consecutivo:
                query = query.filter(RegistroMovimientos.consecutivo == consecutivo)
            if codigo:
                producto = Producto.query.filter_by(codigo=codigo).first()
                if producto:
                    query = query.filter(RegistroMovimientos.producto_id == producto.id)
            if fecha_inicio and fecha_fin:
                query = query.filter(RegistroMovimientos.fecha.between(fecha_inicio, fecha_fin))
            if bodega_origen:
                bodega = Bodega.query.filter_by(nombre=bodega_origen).first()
                if not bodega:
                    return jsonify({'error': f'Bodega de origen {bodega_origen} no encontrada.'}), 404
                query = query.filter(RegistroMovimientos.bodega_origen_id == bodega.id)
            if bodega_destino:
                bodega = Bodega.query.filter_by(nombre=bodega_destino).first()
                if not bodega:
                    return jsonify({'error': f'Bodega de destino {bodega_destino} no encontrada.'}), 404
                query = query.filter(RegistroMovimientos.bodega_destino_id == bodega.id)

            # Agrupar por consecutivo para evitar duplicados
            traslados = query.with_entities(
                RegistroMovimientos.consecutivo,
                db.func.min(RegistroMovimientos.fecha).label("fecha")
            ).group_by(RegistroMovimientos.consecutivo).all()

            if not traslados:
                return jsonify({'error': 'No se encontraron traslados'}), 404

            print(f"Total traslados obtenidos: {len(traslados)}")

            # Crear el PDF
            buffer = BytesIO()
            pdf = canvas.Canvas(buffer, pagesize=letter)
            pdf.setTitle(f"Traslados_{fecha_inicio or 'todos'}_al_{fecha_fin or 'todos'}")

            # Encabezado
            pdf.setFont("Helvetica-Bold", 14)
            pdf.drawString(30, 750, "Traslados Realizados")
            pdf.setFont("Helvetica", 12)
            pdf.drawString(30, 730, f"Rango de fecha: {fecha_inicio or 'Todos'} - {fecha_fin or 'Todos'}")
            pdf.drawString(30, 710, f"Bodega de Origen: {bodega_origen or 'Cualquiera'}")
            pdf.drawString(30, 690, f"Bodega de Destino: {bodega_destino or 'Cualquiera'}")
            pdf.line(30, 670, 570, 670)

            # Tabla
            pdf.setFont("Helvetica-Bold", 10)
            y = 650
            pdf.drawString(30, y, "Consecutivo")
            pdf.drawString(200, y, "Fecha")
            pdf.line(30, y - 5, 570, y - 5)

            pdf.setFont("Helvetica", 10)
            y -= 20
            for traslado in traslados:
                if y < 50:
                    pdf.showPage()
                    pdf.setFont("Helvetica", 10)
                    y = 750
                    pdf.setFont("Helvetica-Bold", 10)
                    pdf.drawString(30, y, "Consecutivo")
                    pdf.drawString(200, y, "Fecha")
                    pdf.line(30, y - 5, 570, y - 5)
                    pdf.setFont("Helvetica", 10)
                    y -= 20

                pdf.drawString(30, y, traslado.consecutivo)
                pdf.drawString(200, y, traslado.fecha.strftime('%Y-%m-%d %H:%M:%S'))
                y -= 15

            pdf.save()
            buffer.seek(0)
            return send_file(
                buffer,
                as_attachment=True,
                download_name=f"traslados_{fecha_inicio or 'todos'}_al_{fecha_fin or 'todos'}.pdf",
                mimetype="application/pdf"
            )
        except Exception as e:
            print(f"Error al generar PDF de traslados: {str(e)}")
            return jsonify({'error': 'Ocurrió un error al generar el PDF.'}), 500


    # Imprimir detalles de un traslado
    @app.route('/api/traslado-detalle-pdf/<consecutivo>', methods=['GET'])
    def generar_traslado_detalle_pdf(consecutivo):
        try:
            traslados = RegistroMovimientos.query.filter_by(
                tipo_movimiento='TRASLADO', consecutivo=consecutivo
            ).all()

            if not traslados:
                return jsonify({'error': 'Traslado no encontrado'}), 404

            buffer = BytesIO()
            pdf = canvas.Canvas(buffer, pagesize=letter)  # Vertical
            pdf.setTitle(f"Traslado_{consecutivo}")

            # Encabezado
            pdf.setFont("Helvetica-Bold", 14)
            pdf.drawString(30, 750, "Traslado entre Bodegas")
            pdf.setFont("Helvetica", 12)
            pdf.drawString(30, 730, f"Número Traslado: {consecutivo}")
            pdf.drawString(30, 710, f"Fecha del Traslado: {traslados[0].fecha.strftime('%Y-%m-%d %H:%M:%S')}")
            pdf.line(30, 700, 570, 700)

            # Tabla
            pdf.setFont("Helvetica-Bold", 10)
            y = 680
            pdf.drawString(30, y, "Producto")
            pdf.drawString(230, y, "Cantidad")
            pdf.drawString(310, y, "Bodega Origen")
            pdf.drawString(420, y, "Bodega Destino")
            pdf.line(30, y - 5, 570, y - 5)

            pdf.setFont("Helvetica", 10)
            y -= 20
            for traslado in traslados:
                if y < 100:  # Reservar espacio para las firmas en una fila (ajustado a 100)
                    pdf.showPage()
                    pdf.setFont("Helvetica", 10)
                    y = 750
                    pdf.setFont("Helvetica-Bold", 10)
                    pdf.drawString(30, y, "Producto")
                    pdf.drawString(230, y, "Cantidad")
                    pdf.drawString(310, y, "Bodega Origen")
                    pdf.drawString(420, y, "Bodega Destino")
                    pdf.line(30, y - 5, 570, y - 5)
                    pdf.setFont("Helvetica", 10)
                    y -= 20

                # Guardar la y inicial de la fila
                y_inicial = y
                producto = Producto.query.get(traslado.producto_id)
                bodega_origen = Bodega.query.get(traslado.bodega_origen_id) if traslado.bodega_origen_id else None
                bodega_destino = Bodega.query.get(traslado.bodega_destino_id) if traslado.bodega_destino_id else None

                # Dibujar columnas sin ajuste
                pdf.drawString(230, y_inicial, str(traslado.cantidad))

                # Dibujar columnas con texto justificado
                y_nueva = draw_wrapped_text_traslado(pdf, 30, y_inicial, producto.nombre if producto else "Desconocido", 200)
                y_nueva = min(y_nueva, draw_wrapped_text_traslado(pdf, 310, y_inicial, bodega_origen.nombre if bodega_origen else "N/A", 110))
                y_nueva = min(y_nueva, draw_wrapped_text_traslado(pdf, 420, y_inicial, bodega_destino.nombre if bodega_destino else "N/A", 150))

                # Ajustar y para la próxima fila
                y = y_nueva - 15

            # Agregar firmas al final en una fila horizontal
            if y < 100:  # Si no hay espacio suficiente, crear nueva página
                pdf.showPage()
                y = 750

            pdf.setFont("Helvetica", 12)
            y -= 40  # Espacio desde la tabla

            # Despachado por (izquierda)
            pdf.line(30, y, 210, y)  # Línea de 180 puntos
            pdf.drawString(30, y - 15, "Despachado por")

            # Entregado por (centro)
            pdf.line(230, y, 410, y)  # Línea de 180 puntos
            pdf.drawString(230, y - 15, "Entregado por")

            # Recibido (derecha)
            pdf.line(430, y, 610, y)  # Línea de 180 puntos
            pdf.drawString(430, y - 15, "Recibido")

            pdf.save()
            buffer.seek(0)
            return send_file(
                buffer,
                as_attachment=True,
                download_name=f"traslado_{consecutivo}.pdf",
                mimetype="application/pdf"
            )
        except Exception as e:
            print(f"Error al generar PDF del detalle del traslado: {str(e)}")
            return jsonify({'error': 'Ocurrió un error al generar el PDF.'}), 500



    @app.route('/api/inventario', methods=['GET'])
    def consultar_inventario_general():
        try:
            offset = int(request.args.get('offset', 0))
            limit = int(request.args.get('limit', 20))
            nombre = request.args.get('nombre')

            bodegas = Bodega.query.all()  # Cambiado de Bodegas a Bodega
            lista_bodegas = {bodega.id: bodega.nombre for bodega in bodegas}

            query = Producto.query
            if nombre:
                query = query.filter(Producto.nombre.ilike(f"{nombre}%"))
            
            productos = query.offset(offset).limit(limit).all()
            if not productos:
                return jsonify({'message': 'No se encontraron productos'}), 200

            resultado = []
            for producto in productos:
                inventario = EstadoInventario.query.filter_by(producto_id=producto.id).all()
                cantidades_por_bodega = {bodega.nombre: 0 for bodega in bodegas}
                for inv in inventario:
                    cantidades_por_bodega[lista_bodegas[inv.bodega_id]] = inv.cantidad
                total_cantidad = sum(cantidades_por_bodega.values())

                resultado.append({
                    'codigo': producto.codigo,
                    'nombre': producto.nombre,
                    'cantidad_total': total_cantidad,
                    'cantidades_por_bodega': cantidades_por_bodega,
                })

            return jsonify({
                'productos': resultado,
                'bodegas': list(lista_bodegas.values()),
            })
        except Exception as e:
            print(f"Error en consultar_inventario_general: {str(e)}")
            return jsonify({'error': 'Error al consultar el inventario general'}), 500


    @app.route('/api/inventario-con-costos', methods=['GET'])
    def consultar_inventario_general_con_costos():
        try:
            offset = int(request.args.get('offset', 0))
            limit = int(request.args.get('limit', 20))
            nombre = request.args.get('nombre')

            bodegas = Bodega.query.all()
            lista_bodegas = {bodega.id: bodega.nombre for bodega in bodegas}

            query = Producto.query
            if nombre:
                query = query.filter(Producto.nombre.ilike(f"{nombre}%"))
            
            productos = query.offset(offset).limit(limit).all()
            if not productos:
                return jsonify({'message': 'No se encontraron productos'}), 200

            resultado = []
            for producto in productos:
                inventario = EstadoInventario.query.filter_by(producto_id=producto.id).all()
                cantidades_por_bodega = {bodega.nombre: 0 for bodega in bodegas}
                costos_por_bodega = {bodega.nombre: 0 for bodega in bodegas}
                for inv in inventario:
                    bodega_nombre = lista_bodegas[inv.bodega_id]
                    cantidades_por_bodega[bodega_nombre] = inv.cantidad
                    ultimo_kardex = db.session.query(Kardex).filter(
                        Kardex.producto_id == producto.id,
                        Kardex.bodega_destino_id == inv.bodega_id
                    ).order_by(Kardex.fecha.desc()).first()
                    costo_unitario = ultimo_kardex.saldo_costo_unitario if ultimo_kardex else 0.0
                    costos_por_bodega[bodega_nombre] = costo_unitario * inv.cantidad

                total_cantidad = sum(cantidades_por_bodega.values())
                resultado.append({
                    'codigo': producto.codigo,
                    'nombre': producto.nombre,
                    'cantidad_total': total_cantidad,
                    'cantidades_por_bodega': cantidades_por_bodega,
                    'costos_por_bodega': costos_por_bodega,
                    'stock_minimo': producto.stock_minimo  # Nuevo campo en la respuesta
                })

            return jsonify({
                'productos': resultado,
                'bodegas': list(lista_bodegas.values()),
            })
        except Exception as e:
            print(f"Error en consultar_inventario_general_con_costos: {str(e)}")
            return jsonify({'error': 'Error al consultar el inventario general'}), 500


    @app.route('/api/ventas', methods=['POST'])
    def cargar_ventas_csv():
        logger.info("Solicitud recibida en /api/ventas")

        if 'file' not in request.files:
            logger.error("No se encontró el archivo en la solicitud")
            return jsonify({'message': 'Archivo no encontrado'}), 400

        file = request.files['file']
        logger.info(f"Archivo recibido: {file.filename}")

        if file.filename == '':
            logger.error("No se seleccionó ningún archivo")
            return jsonify({'message': 'No se seleccionó ningún archivo'}), 400

        stream = TextIOWrapper(file.stream, encoding='utf-8')
        reader = csv.DictReader(stream)

        required_columns = ['factura', 'codigo', 'nombre', 'cantidad', 'fecha_venta', 'bodega']
        missing_columns = [col for col in required_columns if col not in reader.fieldnames]
        if missing_columns:
            logger.error(f"Faltan las columnas obligatorias: {', '.join(missing_columns)}")
            return jsonify({'message': f'Faltan las columnas obligatorias: {", ".join(missing_columns)}'}), 400

        has_precio_unitario = 'precio_unitario' in reader.fieldnames

        # Preconsultar productos, bodegas, estados de inventario y facturas existentes
        productos = {p.codigo: p for p in Producto.query.all()}
        bodegas = {b.nombre: b for b in Bodega.query.all()}
        estados_inventario = {
            (e.producto_id, e.bodega_id): e
            for e in EstadoInventario.query.all()
        }
        ventas_existentes = {
            (v.producto_id, v.bodega_id, v.factura.lower()): v
            for v in Venta.query.all()
        }

        # Preconsultar último Kardex por producto y bodega
        subquery = (
            select(Kardex.producto_id, Kardex.bodega_origen_id, func.max(Kardex.id).label('max_id'))
            .group_by(Kardex.producto_id, Kardex.bodega_origen_id)
            .subquery()
        )
        ultimo_kardex_query = db.session.query(
            Kardex.producto_id,
            Kardex.bodega_origen_id,
            Kardex.saldo_costo_unitario,
            Kardex.saldo_cantidad,
            Kardex.saldo_costo_total
        ).join(
            subquery,
            (Kardex.id == subquery.c.max_id) &
            (Kardex.producto_id == subquery.c.producto_id) &
            (Kardex.bodega_origen_id == subquery.c.bodega_origen_id)
        ).all()
        ultimo_kardex = {
            (k.producto_id, k.bodega_origen_id): k
            for k in ultimo_kardex_query
        }

        # Obtener último consecutivo
        ultimo_consecutivo = db.session.query(func.max(RegistroMovimientos.consecutivo)).scalar() or "T00000"
        consecutivo_base = int(ultimo_consecutivo[1:]) + 1

        # Primera pasada: Validar duplicados dentro del CSV
        stream.seek(0)
        reader = csv.DictReader(stream)
        facturas_csv = {}
        for index, row in enumerate(reader, start=1):
            factura = row.get('factura', '').strip().lower()
            codigo = row.get('codigo', '').strip()
            bodega = row.get('bodega', '').strip()
            if not factura or not codigo or not bodega:
                continue  # Errores de datos se validarán en la segunda pasada
            key = (factura, codigo, bodega)
            if factura not in facturas_csv:
                facturas_csv[factura] = []
            facturas_csv[factura].append((index, key))

        # Validar duplicados dentro del CSV
        errores = []
        for factura, filas in facturas_csv.items():
            seen = set()
            for index, key in filas:
                if key in seen:
                    errores.append(f"Fila {index}: Combinación duplicada de factura {key[0]} con producto {key[1]} y bodega {key[2]} en el CSV.")
                seen.add(key)

        # Identificar productos, bodegas y fechas únicas en el CSV
        stream.seek(0)
        reader = csv.DictReader(stream)
        producto_codigos = set()
        bodega_nombres = set()
        fecha_ventas = set()
        for row in reader:
            producto_codigos.add(row['codigo'].strip())
            bodega_nombres.add(row['bodega'].strip())
            try:
                fecha_ventas.add(datetime.strptime(row['fecha_venta'], '%Y-%m-%d %H:%M:%S'))
            except ValueError:
                continue  # Errores de fecha se validarán en la segunda pasada

        # Mapear códigos a IDs
        producto_ids = {p.id for p in productos.values() if p.codigo in producto_codigos}
        bodega_ids = {b.id for b in bodegas.values() if b.nombre in bodega_nombres}

        # Precalcular saldos disponibles para todas las combinaciones
        saldos = {}
        for fecha_venta in fecha_ventas:
            for producto_id in producto_ids:
                for bodega_id in bodega_ids:
                    saldo = db.session.execute(
                        select(
                            func.sum(
                                case(
                                    (Kardex.tipo_movimiento == 'ENTRADA', Kardex.cantidad),
                                    (Kardex.tipo_movimiento == 'SALIDA', -Kardex.cantidad),
                                    else_=0
                                )
                            ).label('saldo')
                        ).where(
                            Kardex.producto_id == producto_id,
                            Kardex.fecha <= fecha_venta.replace(tzinfo=pytz.timezone('America/Bogota')),
                            (Kardex.bodega_destino_id == bodega_id) | (Kardex.bodega_origen_id == bodega_id)
                        )
                    ).scalar() or 0
                    saldos[(producto_id, bodega_id, fecha_venta)] = saldo

        # Reiniciar el stream para procesar las filas
        stream.seek(0)
        reader = csv.DictReader(stream)

        nuevos_movimientos = []
        nuevos_kardex = []
        nuevas_ventas = []
        filas_procesadas = 0
        max_filas = 10000  # Límite para evitar sobrecarga

        for index, row in enumerate(reader, start=1):
            if filas_procesadas >= max_filas:
                errores.append(f"Se alcanzó el límite de {max_filas} filas. Divida el archivo en partes más pequeñas.")
                break

            try:
                factura = row['factura'].strip()
                if not factura:
                    errores.append(f"Fila {index}: El número de factura es obligatorio y no puede estar vacío.")
                    continue
                if not (factura.startswith('FB') or factura.startswith('CC')):
                    errores.append(f"Fila {index}: El número de factura debe comenzar con 'FB' o 'CC'.")
                    continue

                codigo = row['codigo'].strip()
                nombre = row['nombre'].strip()
                cantidad = row.get('cantidad', '').strip()
                fecha_venta = row['fecha_venta'].strip()
                bodega_nombre = row['bodega'].strip()
                precio_unitario = row['precio_unitario'].strip() if has_precio_unitario else ''

                # Validar datos
                if not codigo:
                    errores.append(f"Fila {index}: El código del producto es obligatorio.")
                    continue
                if not cantidad:
                    errores.append(f"Fila {index}: La cantidad es obligatoria.")
                    continue
                try:
                    cantidad = int(cantidad)
                    if cantidad <= 0:
                        errores.append(f"Fila {index}: La cantidad debe ser mayor que cero.")
                        continue
                except ValueError:
                    errores.append(f"Fila {index}: La cantidad debe ser un número entero.")
                    continue
                if not fecha_venta:
                    errores.append(f"Fila {index}: La fecha de venta es obligatoria.")
                    continue
                try:
                    fecha_venta = datetime.strptime(fecha_venta, '%Y-%m-%d %H:%M:%S')
                except ValueError:
                    errores.append(f"Fila {index}: Formato de fecha inválido. Use 'YYYY-MM-DD HH:MM:SS'.")
                    continue
                if not bodega_nombre:
                    errores.append(f"Fila {index}: La bodega es obligatoria.")
                    continue
                try:
                    precio_unitario = float(precio_unitario) if has_precio_unitario and precio_unitario else None
                except ValueError:
                    errores.append(f"Fila {index}: El precio unitario debe ser un número.")
                    continue

                producto = productos.get(codigo)
                if not producto:
                    errores.append(f"Fila {index}: Producto con código {codigo} no encontrado")
                    continue

                bodega = bodegas.get(bodega_nombre)
                if not bodega:
                    errores.append(f"Fila {index}: Bodega con nombre {bodega_nombre} no encontrada")
                    continue

                # Validar factura duplicada en la base de datos
                if (producto.id, bodega.id, factura.lower()) in ventas_existentes:
                    errores.append(f"Fila {index}: Ya existe una venta con factura {factura} para el producto {codigo} en la bodega {bodega_nombre}.")
                    continue

                # Validar saldo disponible desde los saldos precalculados
                saldo = saldos.get((producto.id, bodega.id, fecha_venta), 0)
                if saldo < cantidad:
                    errores.append(f"Fila {index}: Inventario insuficiente para el producto {codigo} en {bodega_nombre} a la fecha {fecha_venta}. Stock disponible: {saldo}")
                    continue

                # Obtener costo unitario desde último Kardex o EstadoInventario
                ultimo_kardex_entry = ultimo_kardex.get((producto.id, bodega.id))
                estado_inventario = estados_inventario.get((producto.id, bodega.id))

                if ultimo_kardex_entry:
                    costo_unitario = ultimo_kardex_entry.saldo_costo_unitario
                    saldo_cantidad_antes = ultimo_kardex_entry.saldo_cantidad
                    saldo_costo_total_antes = ultimo_kardex_entry.saldo_costo_total
                elif estado_inventario and estado_inventario.costo_unitario:
                    costo_unitario = estado_inventario.costo_unitario
                    saldo_cantidad_antes = estado_inventario.cantidad
                    saldo_costo_total_antes = estado_inventario.costo_total
                else:
                    errores.append(f"Fila {index}: No hay costo unitario inicial para el producto {codigo} en {bodega_nombre}")
                    continue

                costo_total = cantidad * costo_unitario
                saldo_cantidad = saldo_cantidad_antes - cantidad
                saldo_costo_total = saldo_costo_total_antes - costo_total

                # Actualizar EstadoInventario
                if estado_inventario:
                    estado_inventario.cantidad -= cantidad
                    estado_inventario.ultima_actualizacion = fecha_venta
                    estado_inventario.costo_total = estado_inventario.cantidad * estado_inventario.costo_unitario
                else:
                    errores.append(f"Fila {index}: No se encontró estado de inventario para {codigo} en {bodega_nombre}")
                    continue

                # Generar consecutivo
                nuevo_consecutivo = f"T{consecutivo_base + filas_procesadas:05d}"

                # Preparar RegistroMovimientos
                nuevo_movimiento = RegistroMovimientos(
                    consecutivo=nuevo_consecutivo,
                    tipo_movimiento='SALIDA',
                    producto_id=producto.id,
                    bodega_origen_id=bodega.id,
                    bodega_destino_id=None,
                    cantidad=cantidad,
                    fecha=fecha_venta,
                    descripcion=f"Salida de mercancía por venta con Factura {factura} desde {bodega_nombre}",
                    costo_unitario=costo_unitario,
                    costo_total=costo_total
                )
                nuevos_movimientos.append(nuevo_movimiento)

                # Preparar Kardex
                kardex_salida = Kardex(
                    producto_id=producto.id,
                    tipo_movimiento='SALIDA',
                    bodega_origen_id=bodega.id,
                    bodega_destino_id=None,
                    cantidad=cantidad,
                    costo_unitario=costo_unitario,
                    costo_total=costo_total,
                    fecha=fecha_venta.replace(tzinfo=pytz.timezone('America/Bogota')),
                    referencia=f"Salida de mercancía por venta con Factura {factura} desde {bodega_nombre}",
                    saldo_cantidad=saldo_cantidad,
                    saldo_costo_unitario=costo_unitario if saldo_cantidad > 0 else 0.0,
                    saldo_costo_total=saldo_costo_total
                )
                nuevos_kardex.append(kardex_salida)

                # Preparar Venta
                venta = Venta(
                    factura=factura,
                    producto_id=producto.id,
                    nombre_producto=nombre,
                    cantidad=cantidad,
                    fecha_venta=fecha_venta,
                    bodega_id=bodega.id,
                    precio_unitario=precio_unitario
                )
                nuevas_ventas.append(venta)
                ventas_existentes[(producto.id, bodega.id, factura.lower())] = venta

                filas_procesadas += 1

            except Exception as e:
                errores.append(f"Fila {index}: Error procesando la fila ({str(e)})")
                logger.error(f"Fila {index}: Error procesando - {str(e)}")

        if errores:
            logger.error(f"Errores al procesar el archivo: {errores}")
            db.session.rollback()
            return jsonify({'message': 'Errores al procesar el archivo', 'errors': errores}), 400

        try:
            # Insertar en lote y confirmar transacción
            db.session.bulk_save_objects(nuevos_movimientos)
            db.session.bulk_save_objects(nuevos_kardex)
            db.session.bulk_save_objects(nuevas_ventas)
            db.session.commit()
            logger.info("Ventas cargadas correctamente")
            return jsonify({'message': 'Ventas cargadas correctamente'}), 201

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error al guardar en la base de datos: {str(e)}")
            return jsonify({'message': 'Error al guardar los datos', 'errors': [str(e)]}), 500
    

    @app.route('/api/ventas_facturas', methods=['GET'])
    def listar_ventas_facturas():
        try:
            facturas = db.session.query(Venta.factura).distinct().all()
            facturas_lista = [factura[0] for factura in facturas if factura[0]]
            return jsonify({'facturas': facturas_lista})
        except Exception as e:
            print(f"Error al listar facturas de venta: {str(e)}")
            return jsonify({'error': 'Error al listar facturas'}), 500


    @app.route('/api/consultar_ventas', methods=['GET'])
    def consultar_ventas():
        try:
            factura = request.args.get('factura')
            fecha_inicio = request.args.get('fecha_inicio')
            fecha_fin = request.args.get('fecha_fin')
            bodega_id = request.args.get('bodega_id')  # Nuevo filtro

            query = db.session.query(
                Venta.factura,
                db.func.min(Venta.fecha_venta).label('fecha')
            )

            if factura:
                query = query.filter(Venta.factura == factura)
            if fecha_inicio:
                query = query.filter(Venta.fecha_venta >= fecha_inicio)
            if fecha_fin:
                query = query.filter(Venta.fecha_venta <= fecha_fin)
            if bodega_id:
                query = query.filter(Venta.bodega_id == bodega_id)

            query = query.group_by(Venta.factura)
            resultados = query.order_by(db.func.min(Venta.fecha_venta)).all()

            if not resultados:
                return jsonify([])

            response = [
                {
                    'factura': item.factura,
                    'fecha': item.fecha.strftime('%Y-%m-%d %H:%M:%S')
                }
                for item in resultados
            ]
            return jsonify(response)
        except Exception as e:
            print(f"Error al consultar facturas de venta: {str(e)}")
            return jsonify({'error': 'Error al consultar facturas'}), 500


    @app.route('/api/detalle_venta', methods=['GET'])
    def detalle_venta():
        try:
            factura = request.args.get('factura')
            if not factura:
                return jsonify({'error': 'Se requiere el número de factura'}), 400

            query = db.session.query(
                Producto.codigo,
                Venta.nombre_producto.label('nombre'),
                Venta.cantidad,
                Bodega.nombre.label('bodega'),
                Venta.precio_unitario
            ).join(
                Producto, Venta.producto_id == Producto.id
            ).join(
                Bodega, Venta.bodega_id == Bodega.id
            ).filter(
                Venta.factura == factura
            )

            resultados = query.all()

            if not resultados:
                return jsonify([])

            response = [
                {
                    'id': f"{item.codigo}_{index}",
                    'codigo': item.codigo,
                    'nombre': item.nombre,
                    'cantidad': item.cantidad,
                    'bodega': item.bodega,
                    'precio_unitario': float(item.precio_unitario) if item.precio_unitario is not None else None
                }
                for index, item in enumerate(resultados)
            ]
            return jsonify(response)
        except Exception as e:
            print(f"Error al obtener detalle de factura de venta: {str(e)}")
            return jsonify({'error': 'Error al obtener detalle de factura'}), 500


    # Generacion del Kardex
    @app.route('/api/kardex', methods=['GET'])
    def consultar_kardex():
        try:
            codigo_producto = request.args.get('codigo', None)
            fecha_inicio = request.args.get('fecha_inicio', None)
            fecha_fin = request.args.get('fecha_fin', None)
            bodegas = request.args.get('bodegas', None)  # Nuevo parámetro opcional

            if not codigo_producto or not fecha_inicio or not fecha_fin:
                return jsonify({'message': 'Debe proporcionar el código del producto y el rango de fechas'}), 400

            fecha_inicio_dt = datetime.strptime(fecha_inicio, '%Y-%m-%d').replace(tzinfo=timezone.utc)
            fecha_fin_dt = datetime.strptime(fecha_fin, '%Y-%m-%d').replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)

            producto = Producto.query.filter_by(codigo=codigo_producto).first()
            if not producto:
                return jsonify({'message': f'Producto con código {codigo_producto} no encontrado'}), 404

            # Lista de IDs de bodegas si se proporciona el filtro
            bodegas_ids = None
            if bodegas:
                bodegas_list = bodegas.split(',')
                bodegas_ids = [b.id for b in Bodega.query.filter(Bodega.nombre.in_(bodegas_list)).all()]
                if not bodegas_ids:
                    return jsonify({'message': 'Ninguna de las bodegas especificadas fue encontrada'}), 404

            # Obtener saldo inicial antes del rango de consulta
            saldo_bodegas = {}
            saldo_costo_total_bodegas = {}
            kardex_interno_query = Kardex.query.filter(
                Kardex.producto_id == producto.id,
                Kardex.fecha < fecha_inicio_dt
            )
            if bodegas_ids:
                kardex_interno_query = kardex_interno_query.filter(
                    (Kardex.bodega_origen_id.in_(bodegas_ids)) | (Kardex.bodega_destino_id.in_(bodegas_ids))
                )
            kardex_interno = kardex_interno_query.order_by(Kardex.fecha).all()

            for movimiento in kardex_interno:
                if movimiento.tipo_movimiento == 'SALIDA' and movimiento.bodega_origen_id:
                    saldo_bodegas[movimiento.bodega_origen_id] = saldo_bodegas.get(movimiento.bodega_origen_id, 0) - movimiento.cantidad
                    saldo_costo_total_bodegas[movimiento.bodega_origen_id] = saldo_costo_total_bodegas.get(movimiento.bodega_origen_id, 0) - (movimiento.costo_total or 0)
                elif movimiento.tipo_movimiento == 'ENTRADA' and movimiento.bodega_destino_id:
                    saldo_bodegas[movimiento.bodega_destino_id] = saldo_bodegas.get(movimiento.bodega_destino_id, 0) + movimiento.cantidad
                    saldo_costo_total_bodegas[movimiento.bodega_destino_id] = saldo_costo_total_bodegas.get(movimiento.bodega_destino_id, 0) + (movimiento.costo_total or 0)

            saldo_bodegas_nombres = {}
            total_saldo_global = 0
            total_costo_global = 0
            for bodega_id, saldo in saldo_bodegas.items():
                bodega_nombre = db.session.query(Bodega.nombre).filter(Bodega.id == bodega_id).scalar()
                if bodega_nombre and saldo > 0:
                    costo_total = saldo_costo_total_bodegas.get(bodega_id, 0)
                    costo_unitario = costo_total / saldo if saldo > 0 else 0.0
                    saldo_bodegas_nombres[bodega_nombre] = {
                        'cantidad': float(saldo),
                        'costo_total': float(costo_total),
                        'costo_unitario': float(costo_unitario)
                    }
                    total_saldo_global += saldo
                    total_costo_global += costo_total

            saldo_costo_unitario_global = total_costo_global / total_saldo_global if total_saldo_global > 0 else 0.0

            # Consulta de movimientos dentro del rango
            movimientos_query = Kardex.query.filter(
                Kardex.producto_id == producto.id,
                Kardex.fecha >= fecha_inicio_dt,
                Kardex.fecha <= fecha_fin_dt
            )
            if bodegas_ids:
                movimientos_query = movimientos_query.filter(
                    (Kardex.bodega_origen_id.in_(bodegas_ids)) | (Kardex.bodega_destino_id.in_(bodegas_ids))
                )
            movimientos = movimientos_query.order_by(Kardex.fecha).all()

            kardex = []
            saldo_actual = saldo_bodegas.copy()
            saldo_costo_total_actual = saldo_costo_total_bodegas.copy()
            total_saldo_global_actual = total_saldo_global
            total_costo_global_actual = total_costo_global

            # Registrar saldos iniciales por bodega
            for bodega_nombre, saldos in saldo_bodegas_nombres.items():
                kardex.append({
                    'fecha': fecha_inicio_dt.strftime('%Y-%m-%d 00:00:00'),
                    'tipo': 'SALDO INICIAL',
                    'cantidad': saldos['cantidad'],
                    'bodega': bodega_nombre,
                    'saldo': saldos['cantidad'],
                    'costo_unitario': saldos['costo_unitario'],
                    'costo_total': saldos['costo_total'],
                    'saldo_costo_unitario': saldos['costo_unitario'],
                    'saldo_costo_total': saldos['costo_total'],
                    'saldo_costo_unitario_global': saldo_costo_unitario_global,
                    'descripcion': 'Saldo inicial antes del rango de consulta'
                })

            # Registrar movimientos dentro del rango
            for movimiento in movimientos:
                if movimiento.tipo_movimiento == 'ENTRADA' and movimiento.bodega_destino_id:
                    bodega_destino = movimiento.bodega_destino.nombre if movimiento.bodega_destino else None
                    saldo_antes = saldo_actual.get(movimiento.bodega_destino_id, 0)
                    costo_total_antes = saldo_costo_total_actual.get(movimiento.bodega_destino_id, 0)

                    saldo_actual[movimiento.bodega_destino_id] = saldo_antes + movimiento.cantidad
                    costo_total_movimiento = movimiento.costo_total or (movimiento.cantidad * movimiento.costo_unitario)
                    saldo_costo_total_actual[movimiento.bodega_destino_id] = costo_total_antes + costo_total_movimiento
                    total_saldo_global_actual += movimiento.cantidad
                    total_costo_global_actual += costo_total_movimiento

                    saldo_costo_unitario_bodega = (saldo_costo_total_actual[movimiento.bodega_destino_id] / 
                                                saldo_actual[movimiento.bodega_destino_id] if saldo_actual[movimiento.bodega_destino_id] > 0 else 0.0)
                    saldo_costo_unitario_global = total_costo_global_actual / total_saldo_global_actual if total_saldo_global_actual > 0 else 0.0

                    kardex.append({
                        'fecha': movimiento.fecha.strftime('%Y-%m-%d %H:%M:%S'),
                        'tipo': 'ENTRADA',
                        'cantidad': float(movimiento.cantidad),
                        'bodega': bodega_destino,
                        'saldo': float(saldo_actual[movimiento.bodega_destino_id]),
                        'costo_unitario': float(movimiento.costo_unitario or 0.0),
                        'costo_total': float(costo_total_movimiento),
                        'saldo_costo_unitario': float(saldo_costo_unitario_bodega),
                        'saldo_costo_total': float(saldo_costo_total_actual[movimiento.bodega_destino_id]),
                        'saldo_costo_unitario_global': float(saldo_costo_unitario_global),
                        'descripcion': movimiento.referencia or 'Entrada registrada'
                    })

                elif movimiento.tipo_movimiento == 'SALIDA' and movimiento.bodega_origen_id:
                    bodega_origen = movimiento.bodega_origen.nombre if movimiento.bodega_origen else None
                    saldo_antes = saldo_actual.get(movimiento.bodega_origen_id, 0)
                    costo_total_antes = saldo_costo_total_actual.get(movimiento.bodega_origen_id, 0)
                    costo_unitario_antes = costo_total_antes / saldo_antes if saldo_antes > 0 else 0.0

                    saldo_actual[movimiento.bodega_origen_id] = saldo_antes - movimiento.cantidad
                    costo_total_movimiento = movimiento.costo_total or (movimiento.cantidad * (movimiento.costo_unitario or costo_unitario_antes))
                    saldo_costo_total_actual[movimiento.bodega_origen_id] = costo_total_antes - costo_total_movimiento
                    total_saldo_global_actual -= movimiento.cantidad
                    total_costo_global_actual -= costo_total_movimiento

                    saldo_costo_unitario_bodega = (saldo_costo_total_actual[movimiento.bodega_origen_id] / 
                                                saldo_actual[movimiento.bodega_origen_id] if saldo_actual[movimiento.bodega_origen_id] > 0 else costo_unitario_antes)
                    saldo_costo_unitario_global = total_costo_global_actual / total_saldo_global_actual if total_saldo_global_actual > 0 else 0.0

                    saldo_costo_total = float(saldo_costo_total_actual[movimiento.bodega_origen_id]) if saldo_actual[movimiento.bodega_origen_id] > 0 else 0.0

                    kardex.append({
                        'fecha': movimiento.fecha.strftime('%Y-%m-%d %H:%M:%S'),
                        'tipo': 'SALIDA',
                        'cantidad': float(movimiento.cantidad),
                        'bodega': bodega_origen,
                        'saldo': float(saldo_actual[movimiento.bodega_origen_id]),
                        'costo_unitario': float(movimiento.costo_unitario or costo_unitario_antes),
                        'costo_total': float(costo_total_movimiento),
                        'saldo_costo_unitario': float(saldo_costo_unitario_bodega),
                        'saldo_costo_total': saldo_costo_total,
                        'saldo_costo_unitario_global': float(saldo_costo_unitario_global),
                        'descripcion': movimiento.referencia or 'Salida registrada'
                    })

                elif movimiento.tipo_movimiento == 'TRASLADO' and movimiento.bodega_origen_id and movimiento.bodega_destino_id:
                    bodega_origen = movimiento.bodega_origen.nombre if movimiento.bodega_origen else None
                    saldo_origen_antes = saldo_actual.get(movimiento.bodega_origen_id, 0)
                    costo_total_origen_antes = saldo_costo_total_actual.get(movimiento.bodega_origen_id, 0)
                    costo_unitario_origen = costo_total_origen_antes / saldo_origen_antes if saldo_origen_antes > 0 else 0.0
                    costo_total_traslado = movimiento.cantidad * costo_unitario_origen

                    saldo_actual[movimiento.bodega_origen_id] = saldo_origen_antes - movimiento.cantidad
                    saldo_costo_total_actual[movimiento.bodega_origen_id] = costo_total_origen_antes - costo_total_traslado
                    saldo_costo_unitario_origen = (saldo_costo_total_actual[movimiento.bodega_origen_id] / 
                                                saldo_actual[movimiento.bodega_origen_id] if saldo_actual[movimiento.bodega_origen_id] > 0 else costo_unitario_origen)

                    kardex.append({
                        'fecha': movimiento.fecha.strftime('%Y-%m-%d %H:%M:%S'),
                        'tipo': 'SALIDA',
                        'cantidad': float(movimiento.cantidad),
                        'bodega': bodega_origen,
                        'saldo': float(saldo_actual[movimiento.bodega_origen_id]),
                        'costo_unitario': float(costo_unitario_origen),
                        'costo_total': float(costo_total_traslado),
                        'saldo_costo_unitario': float(saldo_costo_unitario_origen),
                        'saldo_costo_total': float(saldo_costo_total_actual[movimiento.bodega_origen_id]),
                        'saldo_costo_unitario_global': float(saldo_costo_unitario_global),
                        'descripcion': f'Traslado con referencia {movimiento.referencia}. Salida de Mercancía de {bodega_origen}'
                    })

                    bodega_destino = movimiento.bodega_destino.nombre if movimiento.bodega_destino else None
                    saldo_destino_antes = saldo_actual.get(movimiento.bodega_destino_id, 0)
                    costo_total_destino_antes = saldo_costo_total_actual.get(movimiento.bodega_destino_id, 0)

                    saldo_actual[movimiento.bodega_destino_id] = saldo_destino_antes + movimiento.cantidad
                    saldo_costo_total_actual[movimiento.bodega_destino_id] = costo_total_destino_antes + costo_total_traslado

                    saldo_costo_unitario_destino = (saldo_costo_total_actual[movimiento.bodega_destino_id] / 
                                                saldo_actual[movimiento.bodega_destino_id] if saldo_actual[movimiento.bodega_destino_id] > 0 else costo_unitario_origen)

                    kardex.append({
                        'fecha': movimiento.fecha.strftime('%Y-%m-%d %H:%M:%S'),
                        'tipo': 'ENTRADA',
                        'cantidad': float(movimiento.cantidad),
                        'bodega': bodega_destino,
                        'saldo': float(saldo_actual[movimiento.bodega_destino_id]),
                        'costo_unitario': float(costo_unitario_origen),
                        'costo_total': float(costo_total_traslado),
                        'saldo_costo_unitario': float(saldo_costo_unitario_destino),
                        'saldo_costo_total': float(saldo_costo_total_actual[movimiento.bodega_destino_id]),
                        'saldo_costo_unitario_global': float(saldo_costo_unitario_global),
                        'descripcion': f'Traslado con referencia {movimiento.referencia}. Entrada de Mercancía a {bodega_destino}'
                    })

            return jsonify({'producto': {'codigo': producto.codigo, 'nombre': producto.nombre}, 'kardex': kardex})

        except Exception as e:
            print(f"❌ Error al consultar Kardex: {str(e)}")
            return jsonify({'error': 'Error al consultar Kardex'}), 500


    # Imprime PDF del Kardex
    @app.route('/api/kardex/pdf', methods=['GET'])
    def generar_kardex_pdf():
        try:
            codigo_producto = request.args.get('codigo')
            fecha_inicio = request.args.get('fecha_inicio')
            fecha_fin = request.args.get('fecha_fin')
            bodegas = request.args.get('bodegas')

            if not codigo_producto or not fecha_inicio or not fecha_fin:
                return jsonify({'error': 'Faltan parámetros (código, fecha_inicio, fecha_fin).'}), 400

            # Reutilizar la lógica de consultar_kardex directamente
            fecha_inicio_dt = datetime.strptime(fecha_inicio, '%Y-%m-%d').replace(tzinfo=timezone.utc)
            fecha_fin_dt = datetime.strptime(fecha_fin, '%Y-%m-%d').replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)

            producto = Producto.query.filter_by(codigo=codigo_producto).first()
            if not producto:
                return jsonify({'message': f'Producto con código {codigo_producto} no encontrado'}), 404

            # Lista de IDs de bodegas si se proporciona el filtro
            bodegas_ids = None
            if bodegas:
                bodegas_list = bodegas.split(',')
                bodegas_ids = [b.id for b in Bodega.query.filter(Bodega.nombre.in_(bodegas_list)).all()]
                if not bodegas_ids:
                    return jsonify({'message': 'Ninguna de las bodegas especificadas fue encontrada'}), 404

            # Obtener saldo inicial antes del rango de consulta
            saldo_bodegas = {}
            saldo_costo_total_bodegas = {}
            kardex_interno_query = Kardex.query.filter(
                Kardex.producto_id == producto.id,
                Kardex.fecha < fecha_inicio_dt
            )
            if bodegas_ids:
                kardex_interno_query = kardex_interno_query.filter(
                    (Kardex.bodega_origen_id.in_(bodegas_ids)) | (Kardex.bodega_destino_id.in_(bodegas_ids))
                )
            kardex_interno = kardex_interno_query.order_by(Kardex.fecha).all()

            for movimiento in kardex_interno:
                if movimiento.tipo_movimiento == 'SALIDA' and movimiento.bodega_origen_id:
                    saldo_bodegas[movimiento.bodega_origen_id] = saldo_bodegas.get(movimiento.bodega_origen_id, 0) - movimiento.cantidad
                    saldo_costo_total_bodegas[movimiento.bodega_origen_id] = saldo_costo_total_bodegas.get(movimiento.bodega_origen_id, 0) - (movimiento.costo_total or 0)
                elif movimiento.tipo_movimiento == 'ENTRADA' and movimiento.bodega_destino_id:
                    saldo_bodegas[movimiento.bodega_destino_id] = saldo_bodegas.get(movimiento.bodega_destino_id, 0) + movimiento.cantidad
                    saldo_costo_total_bodegas[movimiento.bodega_destino_id] = saldo_costo_total_bodegas.get(movimiento.bodega_destino_id, 0) + (movimiento.costo_total or 0)

            saldo_bodegas_nombres = {}
            total_saldo_global = 0
            total_costo_global = 0
            for bodega_id, saldo in saldo_bodegas.items():
                bodega_nombre = db.session.query(Bodega.nombre).filter(Bodega.id == bodega_id).scalar()
                if bodega_nombre and saldo > 0:
                    costo_total = saldo_costo_total_bodegas.get(bodega_id, 0)
                    costo_unitario = costo_total / saldo if saldo > 0 else 0.0
                    saldo_bodegas_nombres[bodega_nombre] = {
                        'cantidad': float(saldo),
                        'costo_total': float(costo_total),
                        'costo_unitario': float(costo_unitario)
                    }
                    total_saldo_global += saldo
                    total_costo_global += costo_total

            saldo_costo_unitario_global = total_costo_global / total_saldo_global if total_saldo_global > 0 else 0.0

            # Consulta de movimientos dentro del rango
            movimientos_query = Kardex.query.filter(
                Kardex.producto_id == producto.id,
                Kardex.fecha >= fecha_inicio_dt,
                Kardex.fecha <= fecha_fin_dt
            )
            if bodegas_ids:
                movimientos_query = movimientos_query.filter(
                    (Kardex.bodega_origen_id.in_(bodegas_ids)) | (Kardex.bodega_destino_id.in_(bodegas_ids))
                )
            movimientos = movimientos_query.order_by(Kardex.fecha).all()

            kardex = []
            saldo_actual = saldo_bodegas.copy()
            saldo_costo_total_actual = saldo_costo_total_bodegas.copy()
            total_saldo_global_actual = total_saldo_global
            total_costo_global_actual = total_costo_global

            # Registrar saldos iniciales por bodega
            for bodega_nombre, saldos in saldo_bodegas_nombres.items():
                kardex.append({
                    'fecha': fecha_inicio_dt.strftime('%Y-%m-%d 00:00:00'),
                    'tipo': 'SALDO INICIAL',
                    'cantidad': saldos['cantidad'],
                    'bodega': bodega_nombre,
                    'saldo': saldos['cantidad'],
                    'costo_unitario': saldos['costo_unitario'],
                    'costo_total': saldos['costo_total'],
                    'saldo_costo_unitario': saldos['costo_unitario'],
                    'saldo_costo_total': saldos['costo_total'],
                    'saldo_costo_unitario_global': saldo_costo_unitario_global,
                    'descripcion': 'Saldo inicial antes del rango de consulta'
                })

            # Registrar movimientos dentro del rango
            for movimiento in movimientos:
                if movimiento.tipo_movimiento == 'ENTRADA' and movimiento.bodega_destino_id:
                    bodega_destino = movimiento.bodega_destino.nombre if movimiento.bodega_destino else None
                    saldo_antes = saldo_actual.get(movimiento.bodega_destino_id, 0)
                    costo_total_antes = saldo_costo_total_actual.get(movimiento.bodega_destino_id, 0)

                    saldo_actual[movimiento.bodega_destino_id] = saldo_antes + movimiento.cantidad
                    costo_total_movimiento = movimiento.costo_total or (movimiento.cantidad * movimiento.costo_unitario)
                    saldo_costo_total_actual[movimiento.bodega_destino_id] = costo_total_antes + costo_total_movimiento
                    total_saldo_global_actual += movimiento.cantidad
                    total_costo_global_actual += costo_total_movimiento

                    saldo_costo_unitario_bodega = (saldo_costo_total_actual[movimiento.bodega_destino_id] / 
                                                saldo_actual[movimiento.bodega_destino_id] if saldo_actual[movimiento.bodega_destino_id] > 0 else 0.0)
                    saldo_costo_unitario_global = total_costo_global_actual / total_saldo_global_actual if total_saldo_global_actual > 0 else 0.0

                    kardex.append({
                        'fecha': movimiento.fecha.strftime('%Y-%m-%d %H:%M:%S'),
                        'tipo': 'ENTRADA',
                        'cantidad': float(movimiento.cantidad),
                        'bodega': bodega_destino,
                        'saldo': float(saldo_actual[movimiento.bodega_destino_id]),
                        'costo_unitario': float(movimiento.costo_unitario or 0.0),
                        'costo_total': float(costo_total_movimiento),
                        'saldo_costo_unitario': float(saldo_costo_unitario_bodega),
                        'saldo_costo_total': float(saldo_costo_total_actual[movimiento.bodega_destino_id]),
                        'saldo_costo_unitario_global': float(saldo_costo_unitario_global),
                        'descripcion': movimiento.referencia or 'Entrada registrada'
                    })

                elif movimiento.tipo_movimiento == 'SALIDA' and movimiento.bodega_origen_id:
                    bodega_origen = movimiento.bodega_origen.nombre if movimiento.bodega_origen else None
                    saldo_antes = saldo_actual.get(movimiento.bodega_origen_id, 0)
                    costo_total_antes = saldo_costo_total_actual.get(movimiento.bodega_origen_id, 0)
                    costo_unitario_antes = costo_total_antes / saldo_antes if saldo_antes > 0 else 0.0

                    saldo_actual[movimiento.bodega_origen_id] = saldo_antes - movimiento.cantidad
                    costo_total_movimiento = movimiento.costo_total or (movimiento.cantidad * (movimiento.costo_unitario or costo_unitario_antes))
                    saldo_costo_total_actual[movimiento.bodega_origen_id] = costo_total_antes - costo_total_movimiento
                    total_saldo_global_actual -= movimiento.cantidad
                    total_costo_global_actual -= costo_total_movimiento

                    saldo_costo_unitario_bodega = (saldo_costo_total_actual[movimiento.bodega_origen_id] / 
                                                saldo_actual[movimiento.bodega_origen_id] if saldo_actual[movimiento.bodega_origen_id] > 0 else costo_unitario_antes)
                    saldo_costo_unitario_global = total_costo_global_actual / total_saldo_global_actual if total_saldo_global_actual > 0 else 0.0

                    saldo_costo_total = float(saldo_costo_total_actual[movimiento.bodega_origen_id]) if saldo_actual[movimiento.bodega_origen_id] > 0 else 0.0

                    kardex.append({
                        'fecha': movimiento.fecha.strftime('%Y-%m-%d %H:%M:%S'),
                        'tipo': 'SALIDA',
                        'cantidad': float(movimiento.cantidad),
                        'bodega': bodega_origen,
                        'saldo': float(saldo_actual[movimiento.bodega_origen_id]),
                        'costo_unitario': float(movimiento.costo_unitario or costo_unitario_antes),
                        'costo_total': float(costo_total_movimiento),
                        'saldo_costo_unitario': float(saldo_costo_unitario_bodega),
                        'saldo_costo_total': saldo_costo_total,
                        'saldo_costo_unitario_global': float(saldo_costo_unitario_global),
                        'descripcion': movimiento.referencia or 'Salida registrada'
                    })

                elif movimiento.tipo_movimiento == 'TRASLADO' and movimiento.bodega_origen_id and movimiento.bodega_destino_id:
                    bodega_origen = movimiento.bodega_origen.nombre if movimiento.bodega_origen else None
                    saldo_origen_antes = saldo_actual.get(movimiento.bodega_origen_id, 0)
                    costo_total_origen_antes = saldo_costo_total_actual.get(movimiento.bodega_origen_id, 0)
                    costo_unitario_origen = costo_total_origen_antes / saldo_origen_antes if saldo_origen_antes > 0 else 0.0
                    costo_total_traslado = movimiento.cantidad * costo_unitario_origen

                    saldo_actual[movimiento.bodega_origen_id] = saldo_origen_antes - movimiento.cantidad
                    saldo_costo_total_actual[movimiento.bodega_origen_id] = costo_total_origen_antes - costo_total_traslado
                    saldo_costo_unitario_origen = (saldo_costo_total_actual[movimiento.bodega_origen_id] / 
                                                saldo_actual[movimiento.bodega_origen_id] if saldo_actual[movimiento.bodega_origen_id] > 0 else costo_unitario_origen)

                    kardex.append({
                        'fecha': movimiento.fecha.strftime('%Y-%m-%d %H:%M:%S'),
                        'tipo': 'SALIDA',
                        'cantidad': float(movimiento.cantidad),
                        'bodega': bodega_origen,
                        'saldo': float(saldo_actual[movimiento.bodega_origen_id]),
                        'costo_unitario': float(costo_unitario_origen),
                        'costo_total': float(costo_total_traslado),
                        'saldo_costo_unitario': float(saldo_costo_unitario_origen),
                        'saldo_costo_total': float(saldo_costo_total_actual[movimiento.bodega_origen_id]),
                        'saldo_costo_unitario_global': float(saldo_costo_unitario_global),
                        'descripcion': f'Traslado con referencia {movimiento.referencia}. Salida de Mercancía de {bodega_origen}'
                    })

                    bodega_destino = movimiento.bodega_destino.nombre if movimiento.bodega_destino else None
                    saldo_destino_antes = saldo_actual.get(movimiento.bodega_destino_id, 0)
                    costo_total_destino_antes = saldo_costo_total_actual.get(movimiento.bodega_destino_id, 0)

                    saldo_actual[movimiento.bodega_destino_id] = saldo_destino_antes + movimiento.cantidad
                    saldo_costo_total_actual[movimiento.bodega_destino_id] = costo_total_destino_antes + costo_total_traslado

                    saldo_costo_unitario_destino = (saldo_costo_total_actual[movimiento.bodega_destino_id] / 
                                                saldo_actual[movimiento.bodega_destino_id] if saldo_actual[movimiento.bodega_destino_id] > 0 else costo_unitario_origen)

                    kardex.append({
                        'fecha': movimiento.fecha.strftime('%Y-%m-%d %H:%M:%S'),
                        'tipo': 'ENTRADA',
                        'cantidad': float(movimiento.cantidad),
                        'bodega': bodega_destino,
                        'saldo': float(saldo_actual[movimiento.bodega_destino_id]),
                        'costo_unitario': float(costo_unitario_origen),
                        'costo_total': float(costo_total_traslado),
                        'saldo_costo_unitario': float(saldo_costo_unitario_destino),
                        'saldo_costo_total': float(saldo_costo_total_actual[movimiento.bodega_destino_id]),
                        'saldo_costo_unitario_global': float(saldo_costo_unitario_global),
                        'descripcion': f'Traslado con referencia {movimiento.referencia}. Entrada de Mercancía a {bodega_destino}'
                    })

            if not kardex:
                bodegas_str = bodegas if bodegas else "todas las bodegas"
                return jsonify({'message': f'No hay movimientos para el producto {codigo_producto} en {bodegas_str} en el rango de fechas seleccionado.'}), 404

            # Generar el PDF
            buffer = BytesIO()
            pdf = canvas.Canvas(buffer, pagesize=landscape(letter))
            pdf.setTitle(f"Kardex_{codigo_producto}")

            # Encabezado
            pdf.setFont("Helvetica-Bold", 12)
            pdf.drawString(30, 550, "Kardex de Inventario")
            pdf.setFont("Helvetica", 10)
            pdf.drawString(30, 535, f"Producto: {producto.nombre} (Código: {producto.codigo})")
            pdf.drawString(30, 520, f"Rango de Fechas: {fecha_inicio} a {fecha_fin}")
            if bodegas:
                bodegas_str = ", ".join(bodegas.split(','))
                pdf.drawString(30, 505, f"Almacenes: {bodegas_str}")
                y = 490
            else:
                pdf.drawString(30, 505, "Almacenes: Todos")
                y = 490

            # Resumen
            almacenes = sorted(list(set(mov['bodega'] for mov in kardex if mov['bodega'])))
            resumen = []
            for almacen in almacenes:
                movimientos_almacen = [m for m in kardex if m['bodega'] == almacen]
                ultimo_mov = max(movimientos_almacen, key=lambda x: x['fecha'])
                resumen.append({
                    'almacen': almacen,
                    'stock_final': ultimo_mov['saldo'],
                    'valor_acumulado': ultimo_mov['saldo_costo_total'],
                    'cpp': ultimo_mov['saldo_costo_unitario'],
                })
            total_stock = sum(r['stock_final'] for r in resumen)
            total_valor = sum(r['valor_acumulado'] for r in resumen)
            cpp_global = total_valor / total_stock if total_stock > 0 else 0

            pdf.setFont("Helvetica-Bold", 10)
            pdf.drawString(30, y, "Resumen por Almacén")
            pdf.line(30, y - 5, 750, y - 5)
            y -= 15
            pdf.drawString(30, y, "CPP GLOBAL")
            pdf.drawString(150, y, f"${cpp_global:.2f}")
            y -= 20

            pdf.setFont("Helvetica-Bold", 8)
            pdf.drawString(30, y, "ALMACÉN")
            pdf.drawString(100, y, "STOCK FINAL")
            pdf.drawString(180, y, "VALOR ACUMULADO")
            pdf.drawString(280, y, "CPP")
            pdf.line(30, y - 5, 350, y - 5)
            y -= 15

            pdf.setFont("Helvetica", 8)
            for r in resumen:
                pdf.drawString(30, y, r['almacen'])
                pdf.drawString(100, y, f"{r['stock_final']:.2f}")
                pdf.drawString(180, y, f"${r['valor_acumulado']:.2f}")
                pdf.drawString(280, y, f"${r['cpp']:.2f}")
                y -= 15
            pdf.setFont("Helvetica-Bold", 8)
            pdf.drawString(30, y, "TOTAL")
            pdf.drawString(100, y, f"{total_stock:.2f}")
            pdf.drawString(180, y, f"${total_valor:.2f}")
            y -= 20

            if y < 50:
                pdf.showPage()
                y = 550

            # Movimientos
            pdf.setFont("Helvetica-Bold", 10)
            pdf.drawString(30, y, "Movimientos del Producto")
            pdf.line(30, y - 5, 750, y - 5)
            y -= 15

            ancho_fecha = 90
            ancho_documento = 60
            ancho_almacen = 60
            ancho_cantidad = 40
            ancho_costo = 50
            ancho_costo_total = 60
            ancho_cantidad_acumulada = 60
            ancho_valor_acumulado = 70
            ancho_cpp = 50
            ancho_cpp_global = 60
            ancho_descripcion = 750 - (ancho_fecha + ancho_documento + ancho_almacen + ancho_cantidad + ancho_costo + 
                                    ancho_costo_total + ancho_cantidad_acumulada + ancho_valor_acumulado + 
                                    ancho_cpp + ancho_cpp_global + 30)

            pdf.setFont("Helvetica-Bold", 7)
            pdf.drawString(30, y, "Fecha")
            pdf.drawString(30 + ancho_fecha, y, "Documento")
            pdf.drawString(30 + ancho_fecha + ancho_documento, y, "Almacén")
            pdf.drawString(30 + ancho_fecha + ancho_documento + ancho_almacen, y, "Cant.")
            pdf.drawString(30 + ancho_fecha + ancho_documento + ancho_almacen + ancho_cantidad, y, "Costo")
            pdf.drawString(30 + ancho_fecha + ancho_documento + ancho_almacen + ancho_cantidad + ancho_costo, y, "Costo Total")
            pdf.drawString(30 + ancho_fecha + ancho_documento + ancho_almacen + ancho_cantidad + ancho_costo + ancho_costo_total, y, "Cant. Acumulada")
            pdf.drawString(30 + ancho_fecha + ancho_documento + ancho_almacen + ancho_cantidad + ancho_costo + ancho_costo_total + ancho_cantidad_acumulada, y, "Valor Acumulado")
            pdf.drawString(30 + ancho_fecha + ancho_documento + ancho_almacen + ancho_cantidad + ancho_costo + ancho_costo_total + ancho_cantidad_acumulada + ancho_valor_acumulado, y, "CPP")
            pdf.drawString(30 + ancho_fecha + ancho_documento + ancho_almacen + ancho_cantidad + ancho_costo + ancho_costo_total + ancho_cantidad_acumulada + ancho_valor_acumulado + ancho_cpp, y, "CPP Global")
            pdf.drawString(30 + ancho_fecha + ancho_documento + ancho_almacen + ancho_cantidad + ancho_costo + ancho_costo_total + ancho_cantidad_acumulada + ancho_valor_acumulado + ancho_cpp + ancho_cpp_global, y, "Descripción")
            pdf.line(30, y - 5, 750, y - 5)
            y -= 15

            pdf.setFont("Helvetica", 6)
            for movimiento in kardex:
                if y < 50:
                    pdf.showPage()
                    pdf.setFont("Helvetica", 6)
                    y = 550
                cantidad = f"-{movimiento['cantidad']:.2f}" if movimiento['tipo'] == "SALIDA" else f"{movimiento['cantidad']:.2f}"
                costo_total = f"-${movimiento['costo_total']:.2f}" if movimiento['tipo'] == "SALIDA" else f"${movimiento['costo_total']:.2f}"
                descripcion = movimiento['descripcion'] or ""
                descripcion_lines = simpleSplit(descripcion, "Helvetica", 6, ancho_descripcion)

                pdf.drawString(30, y, movimiento['fecha'])
                pdf.drawString(30 + ancho_fecha, y, movimiento['tipo'])
                pdf.drawString(30 + ancho_fecha + ancho_documento, y, movimiento['bodega'] or "N/A")
                pdf.drawString(30 + ancho_fecha + ancho_documento + ancho_almacen, y, cantidad)
                pdf.drawString(30 + ancho_fecha + ancho_documento + ancho_almacen + ancho_cantidad, y, f"${movimiento['costo_unitario']:.2f}")
                pdf.drawString(30 + ancho_fecha + ancho_documento + ancho_almacen + ancho_cantidad + ancho_costo, y, costo_total)
                pdf.drawString(30 + ancho_fecha + ancho_documento + ancho_almacen + ancho_cantidad + ancho_costo + ancho_costo_total, y, f"{movimiento['saldo']:.2f}")
                pdf.drawString(30 + ancho_fecha + ancho_documento + ancho_almacen + ancho_cantidad + ancho_costo + ancho_costo_total + ancho_cantidad_acumulada, y, f"${movimiento['saldo_costo_total']:.2f}")
                pdf.drawString(30 + ancho_fecha + ancho_documento + ancho_almacen + ancho_cantidad + ancho_costo + ancho_costo_total + ancho_cantidad_acumulada + ancho_valor_acumulado, y, f"${movimiento['saldo_costo_unitario']:.2f}")
                pdf.drawString(30 + ancho_fecha + ancho_documento + ancho_almacen + ancho_cantidad + ancho_costo + ancho_costo_total + ancho_cantidad_acumulada + ancho_valor_acumulado + ancho_cpp, y, f"${movimiento['saldo_costo_unitario_global']:.2f}")

                # Imprimir descripción con ajuste de líneas
                for i, line in enumerate(descripcion_lines):
                    if i == 0:
                        pdf.drawString(30 + ancho_fecha + ancho_documento + ancho_almacen + ancho_cantidad + ancho_costo + 
                                    ancho_costo_total + ancho_cantidad_acumulada + ancho_valor_acumulado + ancho_cpp + ancho_cpp_global, y, line)
                    else:
                        y -= 12
                        if y < 50:
                            pdf.showPage()
                            pdf.setFont("Helvetica", 6)
                            y = 550
                        pdf.drawString(30 + ancho_fecha + ancho_documento + ancho_almacen + ancho_cantidad + ancho_costo + 
                                    ancho_costo_total + ancho_cantidad_acumulada + ancho_valor_acumulado + ancho_cpp + ancho_cpp_global, y, line)
                y -= 12
                
            pdf.save()
            buffer.seek(0)

            bodegas_str = bodegas.replace(',', '_') if bodegas else ''
            return send_file(
                buffer,
                as_attachment=True,
                download_name=f"kardex_{codigo_producto}{'_' + bodegas_str if bodegas else ''}.pdf",
                mimetype="application/pdf"
            )

        except Exception as e:
            print(f"Error al generar PDF del Kardex: {str(e)}")
            return jsonify({'error': 'Ocurrió un error al generar el PDF del Kardex.'}), 500

# ENDPOINTS ASOCIADOS A LOS PRODUCTOS COMPUESTOS

    #Creacion de Producto Compuesto
    @app.route('/api/productos-compuestos', methods=['POST'])
    def crear_producto_compuesto():
        try:
            data = request.get_json()

            # Crear el producto compuesto
            nuevo_producto = Producto(
                codigo=data['codigo'],
                nombre=data['nombre'],
                codigo_barras=data.get('codigo_barras'), # Almacenar el código de barras
                peso_total_gr=data['peso_total'],  # Usar el peso total enviado desde el frontend
                peso_unidad_gr=data['peso_total'],  # Peso total también como peso unitario
                es_producto_compuesto=True
            )
            db.session.add(nuevo_producto)
            db.session.flush()  # Obtener el ID del producto compuesto

            # Agregar los materiales
            for material in data['materiales']:
                material_producto = MaterialProducto(
                    producto_compuesto_id=nuevo_producto.id,
                    producto_base_id=material['producto_base'],
                    cantidad=material['cantidad'],
                    peso_unitario=material['peso'],
                )
                db.session.add(material_producto)

            db.session.commit()
            return jsonify({'message': 'Producto compuesto creado correctamente'}), 201
        except Exception as e:
            print(f"Error al crear producto compuesto: {str(e)}")
            db.session.rollback()
            return jsonify({'error': 'Error al crear producto compuesto'}), 500


    #Consulta de Producto Compuesto
    @app.route('/api/productos/completos', methods=['GET'])
    def obtener_todos_los_productos():
        """
        Endpoint para devolver todos los productos con información adicional
        que permita distinguir productos compuestos y normales.
        """
        try:
            productos = Producto.query.all()
            if not productos:
                return jsonify({'message': 'No hay productos disponibles'}), 200

            return jsonify([
                {
                    'id': p.id,
                    'codigo': p.codigo,
                    'nombre': p.nombre,
                    'peso_unidad_gr': p.peso_unidad_gr,
                    'es_producto_compuesto': p.es_producto_compuesto
                }
                for p in productos
            ])
        except Exception as e:
            print(f"Error al obtener productos completos: {str(e)}")
            return jsonify({'error': 'Error al obtener productos completos'}), 500


    @app.route('/api/productos-compuestos/detalle', methods=['GET'])
    def buscar_producto_compuesto():
        try:
            codigo = request.args.get('codigo', None)
            producto_id = request.args.get('id', None)
            bodega_id = request.args.get('bodega_id', None)  # Nuevo parámetro para la bodega

            if codigo:
                producto = Producto.query.filter_by(codigo=codigo, es_producto_compuesto=True).first()
            elif producto_id:
                producto = Producto.query.filter_by(id=producto_id, es_producto_compuesto=True).first()
            else:
                return jsonify({'message': 'Debe proporcionar un código o ID...'}), 400

            if not producto:
                return jsonify({'message': 'Producto compuesto no encontrado'}), 404

            materiales = MaterialProducto.query.filter_by(producto_compuesto_id=producto.id).all()
            materiales_response = []
            for material in materiales:
                producto_base = db.session.get(Producto, material.producto_base_id)
                # Obtener el costo unitario desde el último registro en Kardex para la bodega especificada
                query = Kardex.query.filter_by(producto_id=material.producto_base_id)
                if bodega_id:
                    query = query.filter_by(bodega_destino_id=bodega_id)
                ultimo_kardex = query.order_by(Kardex.fecha.desc()).first()
                costo_unitario = float(ultimo_kardex.saldo_costo_unitario) if ultimo_kardex else 0.0

                cantidad = float(material.cantidad) if isinstance(material.cantidad, Decimal) else material.cantidad
                peso_unitario = float(producto_base.peso_unidad_gr) if producto_base.peso_unidad_gr and isinstance(producto_base.peso_unidad_gr, (Decimal, float, int)) else 0.0
                peso_total = cantidad * peso_unitario

                materiales_response.append({
                    'id': material.id,
                    'producto_base_id': material.producto_base_id,
                    'producto_base_codigo': producto_base.codigo,
                    'producto_base_nombre': producto_base.nombre,
                    'cantidad': cantidad,
                    'peso_unitario': peso_unitario,
                    'peso_total': peso_total,
                    'costo_unitario': costo_unitario
                })

            peso_total_gr = float(producto.peso_total_gr) if producto.peso_total_gr and isinstance(producto.peso_total_gr, (Decimal, float, int)) else 0.0
            return jsonify({
                'producto': {
                    'id': producto.id,
                    'codigo': producto.codigo,
                    'nombre': producto.nombre,
                    'codigo_barras': producto.codigo_barras,
                    'peso_total_gr': peso_total_gr,
                },
                'materiales': materiales_response
            }), 200
        except Exception as e:
            print(f"Error al buscar producto compuesto: {str(e)}")
            return jsonify({'error': 'Error al buscar producto compuesto'}), 500


    @app.route('/api/productos-compuestos', methods=['GET'])
    def obtener_productos_compuestos():
        try:
            productos_compuestos = Producto.query.filter_by(es_producto_compuesto=True).all()
            resultado = [
                {
                    'id': producto.id,
                    'nombre': producto.nombre,
                    'codigo': producto.codigo,
                    'peso_total_gr': producto.peso_total_gr
                }
                for producto in productos_compuestos
            ]
            return jsonify(resultado), 200
        except Exception as e:
            print(f"Error al obtener productos compuestos: {str(e)}")
            return jsonify({'error': 'Ocurrió un error al obtener los productos compuestos.'}), 500


    @app.route('/api/productos-compuestos/<int:producto_id>', methods=['GET'])
    def obtener_producto_compuesto(producto_id):
        try:
            producto = Producto.query.filter_by(id=producto_id, es_producto_compuesto=True).first()
            if not producto:
                return jsonify({'message': 'Producto compuesto no encontrado'}), 404

            materiales = MaterialProducto.query.filter_by(producto_compuesto_id=producto_id).all()
            materiales_response = []
            for material in materiales:
                producto_base = db.session.get(Producto, material.producto_base_id)
                materiales_response.append({
                    'id': material.id,
                    'producto_base_id': material.producto_base_id,
                    'producto_base_codigo': producto_base.codigo,
                    'producto_base_nombre': producto_base.nombre,
                    'cantidad': material.cantidad,
                    'peso_unitario': producto_base.peso_unidad_gr,  # Corregir el peso unitario
                    'peso_total': producto_base.peso_unidad_gr * material.cantidad,
                })

            return jsonify(materiales_response), 200
        except Exception as e:
            print(f"Error al obtener el producto compuesto: {str(e)}")
            return jsonify({'error': 'Error al obtener el producto compuesto'}), 500


    @app.route('/api/materiales-producto/<int:material_id>', methods=['PUT'])
    def actualizar_material(material_id):
        try:
            data = request.get_json()
            material = db.session.get(MaterialProducto, material_id)

            if not material:
                return jsonify({'message': 'Material no encontrado'}), 404

            # Actualizar los campos del material
            material.cantidad = data.get('cantidad', material.cantidad)
            material.peso_unitario = data.get('peso_unitario', material.peso_unitario)

            db.session.commit()

            # Recalcular el peso total del producto compuesto
            materiales = MaterialProducto.query.filter_by(
                producto_compuesto_id=material.producto_compuesto_id
            ).all()
            peso_total = sum(m.cantidad * m.peso_unitario for m in materiales)

            # Actualizar el peso total en la tabla productos
            producto = db.session.get(Producto, material.producto_compuesto_id)
            if producto:
                producto.peso_total_gr = peso_total
                producto.peso_unidad_gr = peso_total  # ✅ Sincronizar ambos valores
                db.session.commit()

            return jsonify({'message': 'Material y peso total actualizados correctamente'}), 200
        except Exception as e:
            print(f"Error al actualizar material: {str(e)}")
            db.session.rollback()
            return jsonify({'error': 'Error al actualizar material'}), 500


    @app.route('/api/materiales-producto/<int:material_id>', methods=['DELETE'])
    def eliminar_material(material_id):
        try:
            material = db.session.get(MaterialProducto, material_id)

            if not material:
                return jsonify({'message': 'Material no encontrado'}), 404

            producto_compuesto_id = material.producto_compuesto_id
            db.session.delete(material)
            db.session.commit()

            # Recalcular el peso del producto compuesto después de la eliminación
            recalcular_peso_producto_compuesto(producto_compuesto_id)

            return jsonify({'message': 'Material eliminado correctamente y pesos actualizados.'}), 200
        except Exception as e:
            print(f"Error al eliminar material: {str(e)}")
            db.session.rollback()
            return jsonify({'error': 'Error al eliminar material'}), 500


    # eliminar un producto compuesto
    @app.route('/api/productos-compuestos/<int:producto_id>', methods=['DELETE'])
    def eliminar_producto_compuesto(producto_id):
        try:
            producto = Producto.query.filter_by(id=producto_id, es_producto_compuesto=True).first()
            if not producto:
                return jsonify({'message': 'Producto compuesto no encontrado'}), 404

            # Eliminar materiales relacionados
            MaterialProducto.query.filter_by(producto_compuesto_id=producto_id).delete()
            db.session.delete(producto)
            db.session.commit()

            return jsonify({'message': 'Producto compuesto eliminado correctamente.'}), 200
        except Exception as e:
            print(f"Error al eliminar producto compuesto: {str(e)}")
            db.session.rollback()
            return jsonify({'error': 'Error al eliminar producto compuesto'}), 500

 
    # Endpoint para Obtener Materiales de un Producto Compuesto    
    @app.route('/api/materiales-producto/<int:producto_id>', methods=['GET'])
    def obtener_materiales_producto(producto_id):
        materiales = MaterialProducto.query.filter_by(producto_compuesto_id=producto_id).all()
        
        return jsonify({
            "materiales": [{
                "id": m.id,
                "producto_base_id": m.producto_base_id,
                "cantidad": m.cantidad,
                "peso_unitario": m.peso_unitario,
                "peso_total": m.cantidad * m.peso_unitario
            } for m in materiales]
        })

    #ENDPOINTS CREACION Y MANEJO DE USUARIOS
    # Creacion de usuarios
    @app.route('/api/usuarios', methods=['POST'])
    def guardar_usuario():
        try:
            # Contar los usuarios activos
            total_usuarios = Usuario.query.count()
            if total_usuarios >= MAX_USUARIOS:
                return jsonify({'error': f'No se pueden registrar más usuarios. Límite actual: {MAX_USUARIOS}.'}), 400

            data = request.get_json()

            # Validar datos básicos
            if not data.get('usuario') or not data.get('tipo_usuario'):
                return jsonify({'message': 'Usuario y tipo de usuario son obligatorios'}), 400

            if 'id' in data and data['id']:
                # Editar usuario existente
                usuario = db.session.get(Usuario, data['id'])
                if not usuario:
                    return jsonify({'message': 'Usuario no encontrado'}), 404
            else:
                # Crear nuevo usuario
                usuario = Usuario()
                if not data.get('password'):
                    return jsonify({'message': 'La contraseña es obligatoria para crear un usuario'}), 400
                # Asignar fecha de creación solo al crear un nuevo usuario
                usuario.fecha_creacion = obtener_hora_colombia()

            # Actualizar datos del usuario
            usuario.usuario = data['usuario']
            if 'password' in data and data['password']:
                usuario.password = generate_password_hash(data['password'])  # Encriptar contraseña solo si se proporciona
            usuario.nombres = data['nombres']
            usuario.apellidos = data['apellidos']
            usuario.correo = data.get('correo')
            usuario.celular = data.get('celular')
            usuario.tipo_usuario = data['tipo_usuario']
            usuario.activo = data.get('activo', True)
            usuario.bodega_asignada = data.get('bodega_asignada')

            db.session.add(usuario)
            db.session.commit()
            return jsonify({'message': 'Usuario guardado correctamente'}), 201

        except Exception as e:
            print(f"Error al guardar usuario: {str(e)}")
            db.session.rollback()
            return jsonify({'error': 'Error al guardar usuario'}), 500

        
    # OBTENER USUARIOS
    @app.route('/api/usuarios', methods=['GET'])
    def obtener_usuarios():
        try:
            usuarios = Usuario.query.all()
            return jsonify([{
                'id': u.id,
                'usuario': u.usuario,
                'nombres': u.nombres,
                'apellidos': u.apellidos,
                'correo': u.correo,
                'celular': u.celular,
                'tipo_usuario': u.tipo_usuario,
                'activo': u.activo,
                'fecha_creacion': u.fecha_creacion,
                'bodega_asignada': u.bodega_asignada
            } for u in usuarios])
        except Exception as e:
            print(f"Error al obtener usuarios: {str(e)}")
            return jsonify({'error': 'Error al obtener usuarios'}), 500


    #ENDPOINTS RELATIVOS A PRODUCCION

    # Cargar una orden de producción
    @app.route('/api/ordenes-produccion', methods=['POST'])
    def crear_orden_produccion():
        try:
            data = request.get_json()

            # Validar entrada básica
            if not data.get('producto_compuesto_id') or not data.get('cantidad_paquetes') or not data.get('creado_por') or not data.get('bodega_produccion'):
                return jsonify({'error': 'Datos incompletos. Se requieren producto_compuesto_id, cantidad_paquetes, creado_por y bodega_produccion.'}), 400

            # Verificar si el producto compuesto existe
            producto_compuesto = Producto.query.filter_by(id=data['producto_compuesto_id'], es_producto_compuesto=True).first()
            if not producto_compuesto:
                return jsonify({'error': 'El producto compuesto especificado no existe.'}), 404
            
            # Verificar si la bodega existe (usando db.session.get)
            bodega_produccion = db.session.get(Bodega, data['bodega_produccion'])
            if not bodega_produccion:
                return jsonify({'error': 'La bodega de producción especificada no existe.'}), 404

            # Obtener los materiales necesarios y sus costos desde el Kardex
            materiales = MaterialProducto.query.filter_by(producto_compuesto_id=producto_compuesto.id).all()
            costo_total_materiales = 0
            materiales_detalle = []

            for material in materiales:
                # Obtener el costo unitario desde el último registro en Kardex para la bodega de producción
                ultimo_kardex = Kardex.query.filter_by(
                    producto_id=material.producto_base_id,
                    bodega_destino_id=bodega_produccion.id
                ).order_by(Kardex.fecha.desc()).first()
                costo_unitario = float(ultimo_kardex.saldo_costo_unitario) if ultimo_kardex else 0.0

                # Convertir material.cantidad (Decimal) a float y multiplicar
                cantidad_requerida = float(material.cantidad) * float(data['cantidad_paquetes'])
                costo_material = costo_unitario * cantidad_requerida

                costo_total_materiales += costo_material
                materiales_detalle.append({
                    'producto_base_id': material.producto_base_id,
                    'cantidad': cantidad_requerida,
                    'costo_unitario': costo_unitario,
                    'costo_total': costo_material
                })

            # Calcular el costo unitario del producto compuesto
            costo_unitario_compuesto = costo_total_materiales / float(data['cantidad_paquetes']) if data['cantidad_paquetes'] > 0 else 0

            # Generar el consecutivo de la orden
            ultimo_id = db.session.query(OrdenProduccion.id).order_by(OrdenProduccion.id.desc()).first()
            nuevo_numero_orden = f"OP{str((ultimo_id[0] if ultimo_id else 0) + 1).zfill(8)}"

            # Crear la nueva orden de producción con costos
            nueva_orden = OrdenProduccion(
                producto_compuesto_id=data['producto_compuesto_id'],
                cantidad_paquetes=data['cantidad_paquetes'],
                peso_total=data.get('peso_total'),
                bodega_produccion_id=data['bodega_produccion'],
                creado_por=data['creado_por'],
                numero_orden=nuevo_numero_orden,
                fecha_creacion=obtener_hora_colombia(),
                costo_unitario=costo_unitario_compuesto,
                costo_total=costo_total_materiales
            )
            db.session.add(nueva_orden)
            db.session.commit()

            return jsonify({
                'message': 'Orden de producción creada exitosamente.',
                'orden_id': nueva_orden.id,
                'numero_orden': nueva_orden.numero_orden,
                'costo_unitario': costo_unitario_compuesto,
                'costo_total': costo_total_materiales
            }), 201

        except Exception as e:
            print(f"Error al crear orden de producción: {str(e)}")
            db.session.rollback()
            return jsonify({'error': 'Ocurrió un error al crear la orden de producción.'}), 500


    # Consultar ordenes de produccion por Estado
    @app.route('/api/ordenes-produccion', methods=['GET'])
    def obtener_ordenes_produccion():
        try:
            numero_orden = request.args.get('numero_orden')
            estado = request.args.get('estado')

            query = OrdenProduccion.query

            if numero_orden:
                query = query.filter_by(numero_orden=numero_orden)
            if estado:
                query = query.filter_by(estado=estado)

            ordenes = query.all()

            resultado = []
            for orden in ordenes:
                producto = Producto.query.filter_by(id=orden.producto_compuesto_id).first()
                producto_nombre = f"{producto.codigo} - {producto.nombre}" if producto else "Producto no encontrado"

                resultado.append({
                    "id": orden.id,
                    "numero_orden": orden.numero_orden,
                    "producto_compuesto_id": orden.producto_compuesto_id,
                    "producto_compuesto_nombre": producto_nombre,
                    "cantidad_paquetes": orden.cantidad_paquetes,
                    "estado": orden.estado,
                    "bodega_produccion_id": orden.bodega_produccion_id,
                    "bodega_produccion_nombre": orden.bodega_produccion.nombre if orden.bodega_produccion else "No especificada",
                    "fecha_creacion": orden.fecha_creacion.isoformat() if orden.fecha_creacion else None,
                    "fecha_lista_para_produccion": orden.fecha_lista_para_produccion.isoformat() if orden.fecha_lista_para_produccion else None,
                    "fecha_inicio": orden.fecha_inicio.isoformat() if orden.fecha_inicio else None,
                    "fecha_finalizacion": orden.fecha_finalizacion.isoformat() if orden.fecha_finalizacion else None,
                    "creado_por": orden.creado_por_usuario.nombres if orden.creado_por_usuario else None,
                    "en_produccion_por": orden.en_produccion_por,
                })

            return jsonify(resultado), 200
        except Exception as e:
            print(f"Error al obtener órdenes de producción: {str(e)}")
            return jsonify({'error': 'Ocurrió un error al obtener las órdenes de producción.'}), 500


    # Consultar ordenes y filtar por fechas en modulo de Reportes de Produccion
    # Nuevo endpoint para consultar órdenes de producción con filtros avanzados
    @app.route('/api/ordenes-produccion/filtrar', methods=['GET'])
    def filtrar_ordenes_produccion():
        try:
            numero_orden = request.args.get('numero_orden')
            estado = request.args.get('estado')
            fecha_inicio = request.args.get('fecha_inicio')
            fecha_fin = request.args.get('fecha_fin')

            query = OrdenProduccion.query

            # Filtrar por número de orden
            if numero_orden:
                query = query.filter_by(numero_orden=numero_orden)

            # Filtrar por estado
            if estado:
                query = query.filter_by(estado=estado)

            # Filtrar por rango de fechas (fecha_inicio y fecha_fin)
            if fecha_inicio and fecha_fin:
                query = query.filter(
                    (OrdenProduccion.fecha_creacion.between(fecha_inicio, fecha_fin)) |
                    (OrdenProduccion.fecha_inicio.between(fecha_inicio, fecha_fin)) |
                    (OrdenProduccion.fecha_finalizacion.between(fecha_inicio, fecha_fin))
                )

            ordenes = query.all()

            resultado = [
                {
                    "id": orden.id,
                    "numero_orden": orden.numero_orden,
                    "producto_compuesto_id": orden.producto_compuesto_id,
                    "producto_compuesto_nombre": f"{orden.producto_compuesto.codigo} - {orden.producto_compuesto.nombre}",
                    "cantidad_paquetes": orden.cantidad_paquetes,
                    "estado": orden.estado,
                    "bodega_produccion_id": orden.bodega_produccion_id,
                    "bodega_produccion_nombre": orden.bodega_produccion.nombre,
                    "fecha_creacion": orden.fecha_creacion.isoformat(),
                    "fecha_inicio": orden.fecha_inicio.isoformat() if orden.fecha_inicio else None,
                    "fecha_finalizacion": orden.fecha_finalizacion.isoformat() if orden.fecha_finalizacion else None,
                    "creado_por": orden.creado_por_usuario.nombres if orden.creado_por_usuario else None,
                }
                for orden in ordenes
            ]

            return jsonify(resultado), 200
        except Exception as e:
            print(f"Error al filtrar órdenes de producción: {str(e)}")
            return jsonify({'error': 'Ocurrió un error al filtrar las órdenes de producción.'}), 500


    # Actualizar el Estado de una Orden con validación de inventario
    @app.route('/api/ordenes-produccion/<int:orden_id>/estado', methods=['PUT'])
    def actualizar_estado_orden(orden_id):
        try:
            data = request.get_json()
            nuevo_estado = data.get("nuevo_estado")
            usuario_id = data.get("usuario_id")  # ID del usuario operador

            estados_validos = ["Pendiente", "Lista para Producción", "En Producción", "En Producción-Parcial", "Finalizada"]
            if not nuevo_estado or nuevo_estado not in estados_validos:
                return jsonify({"error": "El estado proporcionado no es válido."}), 400

            orden = db.session.get(OrdenProduccion, orden_id)
            if not orden:
                return jsonify({"error": "Orden de producción no encontrada."}), 404

            # 🚨 Validar si hay suficiente inventario antes de cambiar a "Lista para Producción"
            if nuevo_estado == "Lista para Producción":
                materiales_necesarios = db.session.query(
                    MaterialProducto.producto_base_id, MaterialProducto.cantidad
                ).filter(MaterialProducto.producto_compuesto_id == orden.producto_compuesto_id).all()

                for producto_base_id, cantidad_por_paquete in materiales_necesarios:
                    # 🔹 Cantidad total necesaria = cantidad requerida por paquete * total de paquetes en la orden
                    cantidad_total_requerida = cantidad_por_paquete * orden.cantidad_paquetes

                    # 🔍 Obtener el stock disponible en la bodega de producción
                    inventario_disponible = db.session.query(
                        EstadoInventario.cantidad
                    ).filter(
                        EstadoInventario.producto_id == producto_base_id,
                        EstadoInventario.bodega_id == orden.bodega_produccion_id
                    ).scalar() or 0  # Si no encuentra, asumir 0

                    if inventario_disponible < cantidad_total_requerida:
                        # 🔍 Obtener el código del producto en vez de solo mostrar su ID
                        codigo_producto = db.session.query(Producto.codigo).filter(Producto.id == producto_base_id).scalar()
                        
                        return jsonify({
                            "error": f"El producto con código '{codigo_producto}' no tiene suficiente inventario en la bodega de producción. Se requieren {cantidad_total_requerida}, pero solo hay {inventario_disponible}."
                        }), 400

            # ⏳ Registrar fechas y el operador si el estado cambia
            if nuevo_estado == "Lista para Producción" and not orden.fecha_lista_para_produccion:
                orden.fecha_lista_para_produccion = obtener_hora_colombia()

            if nuevo_estado == "En Producción":
                if not orden.fecha_inicio:
                    orden.fecha_inicio = obtener_hora_colombia()
                if usuario_id:
                    orden.en_produccion_por = usuario_id  # Guardar quién inicia la producción

            if nuevo_estado == "Finalizada" and not orden.fecha_finalizacion:
                orden.fecha_finalizacion = obtener_hora_colombia()

            orden.estado = nuevo_estado
            db.session.commit()

            return jsonify({"message": f"Estado actualizado a {nuevo_estado} correctamente."}), 200

        except Exception as e:
            print(f"Error al actualizar estado: {str(e)}")
            return jsonify({"error": "Ocurrió un error al actualizar el estado."}), 500


    @app.route('/api/ordenes-produccion/<int:orden_id>', methods=['GET'])
    def obtener_detalle_orden_produccion(orden_id):
        try:
            orden = db.session.get(OrdenProduccion, orden_id)
            if not orden:
                return jsonify({'error': f'Orden de producción con ID {orden_id} no encontrada.'}), 404

            materiales = MaterialProducto.query.filter_by(producto_compuesto_id=orden.producto_compuesto_id).all()
            materiales_response = []
            for material in materiales:
                ultimo_kardex = Kardex.query.filter_by(
                    producto_id=material.producto_base_id,
                    bodega_destino_id=orden.bodega_produccion_id
                ).order_by(Kardex.fecha.desc()).first()
                costo_unitario = float(ultimo_kardex.saldo_costo_unitario) if ultimo_kardex else 0.0

                materiales_response.append({
                    'producto_base_id': material.producto_base_id,
                    'producto_base_nombre': f"{material.producto_base.codigo} - {material.producto_base.nombre}",
                    'cant_x_paquete': float(material.cantidad),
                    'peso_x_paquete': float(material.cantidad * material.peso_unitario),
                    'cantidad_total': float(material.cantidad * orden.cantidad_paquetes),
                    'peso_total': float(material.peso_unitario * material.cantidad * orden.cantidad_paquetes),
                    'costo_unitario': costo_unitario,
                    'costo_total': costo_unitario * float(material.cantidad * orden.cantidad_paquetes)
                })

            producido_por = None
            if orden.en_produccion_por:
                usuario = db.session.get(Usuario, orden.en_produccion_por)
                producido_por = f"{usuario.nombres} {usuario.apellidos}" if usuario else "Usuario no encontrado"

            response = {
                'orden': {
                    'id': orden.id,
                    'numero_orden': orden.numero_orden,
                    'producto_compuesto_id': orden.producto_compuesto_id,
                    'producto_compuesto_nombre': f"{orden.producto_compuesto.codigo} - {orden.producto_compuesto.nombre}",
                    'cantidad_paquetes': orden.cantidad_paquetes,
                    'peso_total': orden.peso_total,
                    'estado': orden.estado,
                    'bodega_produccion_id': orden.bodega_produccion_id,
                    'bodega_produccion_nombre': orden.bodega_produccion.nombre,
                    'fecha_creacion': orden.fecha_creacion.isoformat(),
                    'fecha_lista_para_produccion': orden.fecha_lista_para_produccion.isoformat() if orden.fecha_lista_para_produccion else None,
                    'fecha_inicio': orden.fecha_inicio.isoformat() if orden.fecha_inicio else None,
                    'fecha_finalizacion': orden.fecha_finalizacion.isoformat() if orden.fecha_finalizacion else None,
                    'creado_por': f"{orden.creado_por_usuario.nombres} {orden.creado_por_usuario.apellidos}",
                    'producido_por': producido_por,
                    'costo_unitario': float(orden.costo_unitario or 0),
                    'costo_total': float(orden.costo_total or 0),
                    'comentario_cierre_forzado': orden.comentario_cierre_forzado or None
                },
                'materiales': materiales_response,
            }
            return jsonify(response), 200
        except Exception as e:
            print(f"Error al obtener detalles de la orden: {str(e)}")
            return jsonify({'error': 'Ocurrió un error al obtener los detalles.'}), 500


    @app.route('/api/ordenes-produccion/<int:orden_id>/entrega-parcial', methods=['POST'])
    def registrar_entrega_parcial(orden_id):
        try:
            data = request.get_json()
            cantidad_entregada = float(data.get('cantidad_entregada', 0))
            comentario = data.get('comentario', '')

            if cantidad_entregada <= 0:
                return jsonify({'error': 'La cantidad entregada debe ser mayor a 0.'}), 400

            orden = db.session.get(OrdenProduccion, orden_id)
            if not orden or orden.estado == "Finalizada":
                return jsonify({'error': 'Orden no válida.'}), 400

            materiales = MaterialProducto.query.filter_by(producto_compuesto_id=orden.producto_compuesto_id).all()
            for material in materiales:
                cantidad_consumida = abs(float(material.cantidad)) * float(cantidad_entregada)
                ultimo_kardex = Kardex.query.filter(
                    Kardex.producto_id == material.producto_base_id,
                    (Kardex.bodega_origen_id == orden.bodega_produccion_id) | (Kardex.bodega_destino_id == orden.bodega_produccion_id)
                ).order_by(Kardex.fecha.desc()).first()

                saldo_cantidad = float(ultimo_kardex.saldo_cantidad) if ultimo_kardex else 0.0
                costo_unitario = float(ultimo_kardex.saldo_costo_unitario) if ultimo_kardex else 0.0
                saldo_costo_total = float(ultimo_kardex.saldo_costo_total) if ultimo_kardex else 0.0

                kardex_salida = Kardex(
                    producto_id=material.producto_base_id,
                    bodega_origen_id=orden.bodega_produccion_id,
                    fecha=obtener_hora_colombia(),
                    tipo_movimiento='SALIDA',
                    cantidad=cantidad_consumida,  # Positivo, frontend lo muestra negativo
                    costo_unitario=costo_unitario,
                    costo_total=costo_unitario * cantidad_consumida,
                    saldo_cantidad=saldo_cantidad - cantidad_consumida,  # Resta explícita
                    saldo_costo_unitario=costo_unitario,
                    saldo_costo_total=saldo_costo_total - (costo_unitario * cantidad_consumida),
                    referencia=f"Consumo para orden {orden.numero_orden}"
                )
                db.session.add(kardex_salida)
                actualizar_estado_inventario(material.producto_base_id, orden.bodega_produccion_id, cantidad_consumida, es_entrada=False)

            ultimo_kardex_compuesto = Kardex.query.filter(
                Kardex.producto_id == orden.producto_compuesto_id,
                Kardex.bodega_destino_id == orden.bodega_produccion_id
            ).order_by(Kardex.fecha.desc()).first()
            saldo_cantidad_compuesto = float(ultimo_kardex_compuesto.saldo_cantidad) if ultimo_kardex_compuesto else 0.0
            costo_unitario_compuesto = float(orden.costo_unitario or 0)

            kardex_entrada = Kardex(
                producto_id=orden.producto_compuesto_id,
                bodega_destino_id=orden.bodega_produccion_id,
                fecha=obtener_hora_colombia(),
                tipo_movimiento='ENTRADA',
                cantidad=cantidad_entregada,
                costo_unitario=costo_unitario_compuesto,
                costo_total=costo_unitario_compuesto * cantidad_entregada,
                saldo_cantidad=saldo_cantidad_compuesto + cantidad_entregada,
                saldo_costo_unitario=costo_unitario_compuesto,
                saldo_costo_total=(saldo_cantidad_compuesto + cantidad_entregada) * costo_unitario_compuesto,
                referencia=f"Producción parcial de orden {orden.numero_orden}"
            )
            db.session.add(kardex_entrada)
            actualizar_estado_inventario(orden.producto_compuesto_id, orden.bodega_produccion_id, cantidad_entregada, es_entrada=True)

            entrega = EntregaParcial(
                orden_produccion_id=orden_id,
                cantidad_entregada=cantidad_entregada,
                fecha_entrega=obtener_hora_colombia(),
                comentario=comentario
            )
            db.session.add(entrega)

            entregas_totales = db.session.query(func.sum(EntregaParcial.cantidad_entregada))\
                .filter_by(orden_produccion_id=orden.id).scalar() or 0
            cantidad_pendiente = float(orden.cantidad_paquetes) - float(entregas_totales)

            if cantidad_pendiente <= 0:
                orden.estado = "Finalizada"
                orden.fecha_finalizacion = obtener_hora_colombia()
            else:
                orden.estado = "En Producción-Parcial"

            db.session.commit()
            return jsonify({'message': 'Entrega parcial registrada con éxito.', 'cantidad_pendiente': cantidad_pendiente}), 200

        except Exception as e:
            db.session.rollback()
            print(f"Error: {e}")
            return jsonify({'error': 'Error al registrar entrega parcial.'}), 500


    @app.route('/api/ordenes-produccion/<int:orden_id>/registrar-entrega-total', methods=['POST'])
    def registrar_entrega_total(orden_id):
        try:
            orden = db.session.get(OrdenProduccion, orden_id)
            if not orden or orden.estado not in ["En Producción", "En Producción-Parcial"]:
                return jsonify({'error': 'La orden no está en estado válido para registrar entrega total.'}), 400

            cantidad_entregada = orden.cantidad_paquetes - (
                db.session.query(func.sum(EntregaParcial.cantidad_entregada))
                .filter_by(orden_produccion_id=orden.id)
                .scalar() or 0
            )

            if cantidad_entregada <= 0:
                return jsonify({'error': 'No hay cantidad pendiente para registrar entrega total.'}), 400

            # Registrar salidas de materiales en Kardex
            materiales = MaterialProducto.query.filter_by(producto_compuesto_id=orden.producto_compuesto_id).all()
            for material in materiales:
                cantidad_consumida = abs(float(material.cantidad)) * float(cantidad_entregada)  # Positiva
                ultimo_kardex = Kardex.query.filter(
                    Kardex.producto_id == material.producto_base_id,
                    (Kardex.bodega_origen_id == orden.bodega_produccion_id) | (Kardex.bodega_destino_id == orden.bodega_produccion_id)
                ).order_by(Kardex.fecha.desc()).first()
                costo_unitario = float(ultimo_kardex.saldo_costo_unitario) if ultimo_kardex else 0.0
                saldo_cantidad_actual = float(ultimo_kardex.saldo_cantidad) if ultimo_kardex else 0.0
                saldo_costo_total_actual = float(ultimo_kardex.saldo_costo_total) if ultimo_kardex else 0.0

                kardex_salida = Kardex(
                    producto_id=material.producto_base_id,
                    bodega_origen_id=orden.bodega_produccion_id,
                    fecha=obtener_hora_colombia(),
                    tipo_movimiento='SALIDA',
                    cantidad=cantidad_consumida,  # Positiva, frontend la muestra negativa
                    costo_unitario=costo_unitario,
                    costo_total=costo_unitario * cantidad_consumida,
                    saldo_cantidad=saldo_cantidad_actual - cantidad_consumida,  # Resta explícita
                    saldo_costo_unitario=costo_unitario,
                    saldo_costo_total=saldo_costo_total_actual - (costo_unitario * cantidad_consumida),
                    referencia=f"Consumo para orden {orden.numero_orden}"
                )
                db.session.add(kardex_salida)
                # Actualizar estado_inventario para el material
                actualizar_estado_inventario(material.producto_base_id, orden.bodega_produccion_id, cantidad_consumida, es_entrada=False)

            # Registrar entrada del producto compuesto en Kardex
            ultimo_kardex_compuesto = Kardex.query.filter(
                Kardex.producto_id == orden.producto_compuesto_id,
                Kardex.bodega_destino_id == orden.bodega_produccion_id
            ).order_by(Kardex.fecha.desc()).first()
            saldo_cantidad_compuesto = float(ultimo_kardex_compuesto.saldo_cantidad) if ultimo_kardex_compuesto else 0.0
            costo_unitario_compuesto = float(orden.costo_unitario or 0)

            kardex_entrada = Kardex(
                producto_id=orden.producto_compuesto_id,
                bodega_destino_id=orden.bodega_produccion_id,
                fecha=obtener_hora_colombia(),
                tipo_movimiento='ENTRADA',
                cantidad=float(cantidad_entregada),  # Positiva
                costo_unitario=costo_unitario_compuesto,
                costo_total=costo_unitario_compuesto * float(cantidad_entregada),
                saldo_cantidad=saldo_cantidad_compuesto + float(cantidad_entregada),  # Suma explícita
                saldo_costo_unitario=costo_unitario_compuesto,
                saldo_costo_total=(saldo_cantidad_compuesto + float(cantidad_entregada)) * costo_unitario_compuesto,
                referencia=f"Producción total de orden {orden.numero_orden}"
            )
            db.session.add(kardex_entrada)
            # Actualizar estado_inventario para el producto compuesto
            actualizar_estado_inventario(orden.producto_compuesto_id, orden.bodega_produccion_id, float(cantidad_entregada), es_entrada=True)

            # Registrar entrega en entregas_parciales
            entrega = EntregaParcial(
                orden_produccion_id=orden_id,
                cantidad_entregada=float(cantidad_entregada),
                fecha_entrega=obtener_hora_colombia(),
                comentario="Entrega total en bodega registrada automáticamente"
            )
            db.session.add(entrega)

            # Finalizar la orden
            orden.estado = "Finalizada"
            orden.fecha_finalizacion = obtener_hora_colombia()

            db.session.commit()
            return jsonify({'message': 'Entrega total registrada y orden finalizada con éxito.'}), 200

        except ValueError as ve:
            db.session.rollback()
            return jsonify({'error': str(ve)}), 400
        except Exception as e:
            db.session.rollback()
            print(f"Error al registrar entrega total: {str(e)}")
            return jsonify({'error': 'Ocurrió un error al registrar la entrega total.'}), 500
        

    @app.route('/api/ordenes-produccion/<int:orden_id>/estado/en-produccion', methods=['PUT'])
    def actualizar_estado_en_produccion(orden_id):
        try:
            # Buscar la orden de producción por ID
            orden = OrdenProduccion.db.session.get(orden_id)

            if not orden:
                return jsonify({'error': f'Orden de producción con ID {orden_id} no encontrada.'}), 404

            # Validar que la orden esté lista para producción antes de cambiar el estado
            if orden.estado != "Lista para Producción":
                return jsonify({'error': f'La orden de producción no está en estado: Lista para Producción.'}), 400

            # Actualizar el estado de la orden
            orden.estado = "En Producción"
            orden.fecha_inicio = obtener_hora_colombia()
            db.session.commit()

            return jsonify({'message': 'Estado de la orden actualizado a En Producción exitosamente.'}), 200
        except Exception as e:
            print(f"Error al actualizar estado a En Producción: {str(e)}")
            return jsonify({'error': 'Ocurrió un error al actualizar el estado de la orden.'}), 500

    # Registrar Producción Parcial o Completa
    @app.route('/api/ordenes-produccion/<int:orden_id>/registrar-produccion', methods=['POST'])
    def registrar_produccion(orden_id):
        try:
            data = request.get_json()
            cantidad_producida = data.get('cantidad_producida')
            bodega_destino_id = data.get('bodega_destino_id')
            usuario_id = data.get('usuario_id')  # Registrar el usuario que realiza la entrega

            if cantidad_producida <= 0:
                return jsonify({'error': 'La cantidad producida debe ser mayor a cero.'}), 400

            orden = db.session.get(OrdenProduccion, orden_id)
            if not orden:
                return jsonify({'error': f'Orden de producción con ID {orden_id} no encontrada.'}), 404

            if orden.estado not in ["En Producción", "En Producción-Parcial"]:
                return jsonify({'error': 'La orden no está en estado válido para registrar producción.'}), 400

            if cantidad_producida > orden.cantidad_paquetes:
                return jsonify({'error': 'La cantidad producida excede la cantidad pendiente.'}), 400

            # Registrar la entrega parcial
            detalle = DetalleProduccion(
                orden_produccion_id=orden.id,
                producto_base_id=orden.producto_compuesto_id,
                cantidad_producida=cantidad_producida,
                bodega_destino_id=bodega_destino_id,
                fecha_registro=obtener_hora_colombia(),
                registrado_por=usuario_id
            )
            db.session.add(detalle)

            # Actualizar cantidad pendiente y estado de la orden
            orden.cantidad_paquetes -= cantidad_producida
            if orden.cantidad_paquetes == 0:
                orden.estado = "Finalizada"
                orden.fecha_finalizacion = obtener_hora_colombia()
            else:
                orden.estado = "En Producción-Parcial"

            db.session.commit()

            return jsonify({
                'message': 'Producción registrada exitosamente.',
                'cantidad_entregada': cantidad_producida,
                'cantidad_pendiente': orden.cantidad_paquetes,
                'estado_actual': orden.estado
            }), 200
        except Exception as e:
            print(f"Error al registrar producción: {str(e)}")
            db.session.rollback()
            return jsonify({'error': 'Ocurrió un error al registrar la producción.'}), 500


    # ENPOINT PARA REGISTRAR UN CIERRE FORZADO
    @app.route('/api/ordenes-produccion/<int:orden_id>/cierre-forzado', methods=['POST'])
    def cierre_forzado(orden_id):
        try:
            data = request.get_json()
            comentario_usuario = data.get("comentario", "").strip()

            orden = db.session.get(OrdenProduccion, orden_id)
            if not orden:
                return jsonify({'error': 'Orden no encontrada.'}), 404

            if orden.estado != "En Producción-Parcial":
                return jsonify({'error': 'Solo se pueden cerrar órdenes en estado "En Producción-Parcial".'}), 400

            comentario_final = comentario_usuario if comentario_usuario else "Cierre forzado sin comentario adicional"

            # Obtener el último saldo del producto compuesto en Kardex
            ultimo_kardex = Kardex.query.filter(
                Kardex.producto_id == orden.producto_compuesto_id,
                Kardex.bodega_destino_id == orden.bodega_produccion_id
            ).order_by(Kardex.fecha.desc()).first()

            saldo_cantidad = float(ultimo_kardex.saldo_cantidad) if ultimo_kardex else 0.0
            costo_unitario = float(ultimo_kardex.saldo_costo_unitario) if ultimo_kardex else float(orden.costo_unitario or 0)
            
            # Calcular el costo total REAL basado en lo producido hasta el momento
            saldo_costo_total = saldo_cantidad * costo_unitario

            # Obtener la cantidad total producida para esta orden específica
            entregas = db.session.query(func.sum(EntregaParcial.cantidad_entregada)).filter_by(orden_produccion_id=orden_id).scalar() or 0
            costo_total_real = float(entregas) * costo_unitario

            kardex_cierre = Kardex(
                producto_id=orden.producto_compuesto_id,
                bodega_destino_id=orden.bodega_produccion_id,
                fecha=obtener_hora_colombia(),
                tipo_movimiento='ENTRADA',
                cantidad=0,
                costo_unitario=costo_unitario,
                costo_total=0,
                saldo_cantidad=saldo_cantidad,
                saldo_costo_unitario=costo_unitario,
                saldo_costo_total=saldo_costo_total,
                referencia=f"Cierre forzado de orden {orden.numero_orden}"
            )
            db.session.add(kardex_cierre)

            # Actualizar estado_inventario con el costo total global
            estado_inv = EstadoInventario.query.filter_by(
                producto_id=orden.producto_compuesto_id,
                bodega_id=orden.bodega_produccion_id
            ).first()
            if estado_inv:
                estado_inv.cantidad = saldo_cantidad
                estado_inv.costo_total = saldo_costo_total
                estado_inv.ultima_actualizacion = obtener_hora_colombia()

            # Ajustar el costo_total de la orden al costo real de lo producido
            orden.costo_total = costo_total_real
            orden.estado = "Finalizada"
            orden.fecha_finalizacion = obtener_hora_colombia()
            orden.comentario_cierre_forzado = comentario_final

            db.session.commit()

            return jsonify({
                'message': 'Cierre forzado realizado con éxito.',
                'comentario': comentario_final,
                'costo_total_real': costo_total_real
            }), 200

        except Exception as e:
            db.session.rollback()
            print(f"Error al realizar el cierre forzado: {e}")
            return jsonify({'error': 'No se pudo completar el cierre forzado.'}), 500


    # Consultar Producción Registrada
    @app.route('/api/ordenes-produccion/<int:orden_id>/produccion', methods=['GET'])
    def consultar_produccion(orden_id):
        try:
            # Obtener la orden de producción
            orden = OrdenProduccion.db.session.get(orden_id)
            if not orden:
                return jsonify({"error": f"Orden de producción con ID {orden_id} no encontrada."}), 404

            # Obtener los detalles de producción asociados a la orden
            detalles = DetalleProduccion.query.filter_by(orden_produccion_id=orden_id).all()

            # Construir la respuesta
            produccion = []
            for detalle in detalles:
                bodega_destino = Bodega.db.session.get(detalle.bodega_destino_id)
                producto_base = Producto.db.session.get(detalle.producto_base_id)

                produccion.append({
                    "id": detalle.id,
                    "producto_base_id": detalle.producto_base_id,
                    "producto_base_nombre": producto_base.nombre if producto_base else None,
                    "cantidad_consumida": detalle.cantidad_consumida,
                    "cantidad_producida": detalle.cantidad_producida,
                    "bodega_destino_id": detalle.bodega_destino_id,
                    "bodega_destino_nombre": bodega_destino.nombre if bodega_destino else None,
                    "fecha_registro": detalle.fecha_registro
                })

            return jsonify({
                "orden": {
                    "id": orden.id,
                    "producto_compuesto_id": orden.producto_compuesto_id,
                    "producto_compuesto_nombre": orden.producto_compuesto.nombre if orden.producto_compuesto else None,
                    "estado": orden.estado,
                    "bodega_produccion_id": orden.bodega_produccion_id,
                    "bodega_produccion_nombre": orden.bodega_produccion.nombre if orden.bodega_produccion else None,
                    "fecha_creacion": orden.fecha_creacion,
                    "fecha_inicio": orden.fecha_inicio,
                    "fecha_finalizacion": orden.fecha_finalizacion
                },
                "produccion": produccion
            })
        except Exception as e:
            print(f"Error al consultar producción: {str(e)}")
            return jsonify({"error": "Ocurrió un error al consultar la producción."}), 500


    # Consultar historial de producción
    @app.route('/api/ordenes-produccion/historial', methods=['GET'])
    def historial_produccion():
        try:
            estado = request.args.get('estado')
            fecha_inicio = request.args.get('fecha_inicio')
            fecha_fin = request.args.get('fecha_fin')

            query = OrdenProduccion.query

            # Filtrar por estado si se proporciona
            if estado:
                query = query.filter_by(estado=estado)

            # Filtrar por rango de fechas si se proporciona
            if fecha_inicio:
                query = query.filter(OrdenProduccion.fecha_creacion >= fecha_inicio)
            if fecha_fin:
                query = query.filter(OrdenProduccion.fecha_creacion <= fecha_fin)

            ordenes = query.order_by(OrdenProduccion.fecha_creacion.desc()).all()

            resultado = []
            for orden in ordenes:
                resultado.append({
                    'id': orden.id,
                    'producto_compuesto_id': orden.producto_compuesto_id,
                    'producto_compuesto_nombre': orden.producto_compuesto.nombre,
                    'cantidad_paquetes': orden.cantidad_paquetes,
                    'estado': orden.estado,
                    'bodega_produccion_id': orden.bodega_produccion_id,
                    'bodega_produccion_nombre': orden.bodega.nombre,
                    'fecha_creacion': orden.fecha_creacion,
                    'fecha_inicio': orden.fecha_inicio,
                    'fecha_finalizacion': orden.fecha_finalizacion
                })

            return jsonify({'historial': resultado}), 200

        except Exception as e:
            print(f"Error al consultar historial de producción: {str(e)}")
            return jsonify({'error': 'Ocurrió un error al consultar el historial de producción.'}), 500

    @app.route('/api/ordenes-produccion/<int:orden_id>/historial-entregas', methods=['GET'])
    def obtener_historial_entregas(orden_id):
        try:
            # Verificar si la orden existe
            orden = db.session.get(OrdenProduccion, orden_id)
            if not orden:
                return jsonify({'error': f'Orden de producción con ID {orden_id} no encontrada.'}), 404

            # Consultar las entregas parciales relacionadas con la orden
            entregas = db.session.query(EntregaParcial).filter_by(orden_produccion_id=orden_id).all()

            historial_response = [
                {
                    'cantidad': entrega.cantidad_entregada,
                    'fecha_hora': entrega.fecha_entrega.isoformat(),  # Formato ISO para las fechas
                    'comentario': entrega.comentario
                }
                for entrega in entregas
            ]

            # Calcular la cantidad total entregada y pendiente
            total_entregado = sum(entrega.cantidad_entregada for entrega in entregas)
            cantidad_pendiente = max(orden.cantidad_paquetes - total_entregado, 0)

            return jsonify({
                'historial': historial_response,
                'total_entregado': total_entregado,
                'cantidad_pendiente': cantidad_pendiente
            }), 200

        except Exception as e:
            print(f"Error al obtener historial de entregas: {str(e)}")
            return jsonify({'error': 'Ocurrió un error al obtener el historial de entregas.'}), 500


    # Eliminar orden de producción
    @app.route('/api/ordenes-produccion/<int:orden_id>', methods=['DELETE'])
    def eliminar_orden_produccion(orden_id):
        try:
            # Buscar la orden
            orden = OrdenProduccion.query.get(orden_id)
            if not orden:
                return jsonify({'error': 'Orden no encontrada.'}), 404
            
            # Verificar si el estado es "Pendiente" o "Lista para Producir"
            if orden.estado not in ['Pendiente', 'Lista para Producción']:
                return jsonify({'error': 'No se puede eliminar la orden en este estado.'}), 400

            # Eliminar la orden
            db.session.delete(orden)
            db.session.commit()

            return jsonify({'message': 'Orden eliminada exitosamente.'}), 200

        except Exception as e:
            db.session.rollback()
            print(f"Error al eliminar la orden: {str(e)}")
            return jsonify({'error': 'Ocurrió un error al eliminar la orden.'}), 500


    # Actualizar información de una orden de producción que aun no se haya iniciado
    @app.route('/api/ordenes-produccion/<int:orden_id>', methods=['PUT'])
    def actualizar_orden_produccion(orden_id):
        try:
            data = request.get_json()

            orden = OrdenProduccion.db.session.get(orden_id)

            if not orden:
                return jsonify({'error': f'Orden de producción con ID {orden_id} no encontrada.'}), 404

            if orden.estado != "Pendiente":
                return jsonify({'error': 'Solo se pueden actualizar órdenes en estado Pendiente.'}), 400

            # Actualizar campos permitidos
            if 'cantidad_paquetes' in data:
                orden.cantidad_paquetes = data['cantidad_paquetes']

            if 'peso_total' in data:
                orden.peso_total = data['peso_total']

            if 'bodega_produccion_id' in data:
                bodega = Bodega.db.session.get(data['bodega_produccion_id'])
                if not bodega:
                    return jsonify({'error': f'Bodega con ID {data["bodega_produccion_id"]} no encontrada.'}), 404
                orden.bodega_produccion_id = data['bodega_produccion_id']

            db.session.commit()

            return jsonify({'message': 'Orden de producción actualizada correctamente.'}), 200

        except Exception as e:
            print(f"Error al actualizar orden de producción: {str(e)}")
            db.session.rollback()
            return jsonify({'error': 'Ocurrió un error al actualizar la orden de producción.'}), 500


    @app.route('/api/ordenes-produccion/<int:orden_id>/pdf', methods=['GET'])
    def generar_pdf_orden(orden_id):
        try:
            # Consultar la orden de producción
            orden = db.session.get(OrdenProduccion, orden_id)
            if not orden:
                return jsonify({'error': 'Orden de producción no encontrada'}), 404

            # Consultar el usuario creador
            usuario_creador = db.session.get(Usuario, orden.creado_por)
            nombre_creador = f"{usuario_creador.nombres} {usuario_creador.apellidos}" if usuario_creador else "Desconocido"

            # Consultar el usuario que produjo la orden
            usuario_productor = db.session.get(Usuario, orden.en_produccion_por)
            nombre_productor = f"{usuario_productor.nombres} {usuario_productor.apellidos}" if usuario_productor else "N/A"

            # Verificar si la orden tuvo un cierre forzado
            tiene_cierre_forzado = bool(orden.comentario_cierre_forzado)
            comentario_cierre_forzado = orden.comentario_cierre_forzado or "Orden finalizada sin novedad."

            # Consultar los materiales del producto compuesto
            materiales_producto = db.session.query(MaterialProducto).filter_by(
                producto_compuesto_id=orden.producto_compuesto_id
            ).all()

            # Consultar el historial de entregas y calcular cantidad pendiente
            entregas_parciales = db.session.query(EntregaParcial).filter_by(
                orden_produccion_id=orden_id
            ).all()
            entregas_totales = sum(entrega.cantidad_entregada for entrega in entregas_parciales)
            cantidad_pendiente = orden.cantidad_paquetes - entregas_totales

            # Configuración del PDF con orientación horizontal
            buffer = BytesIO()
            pdf = canvas.Canvas(buffer, pagesize=landscape(letter))
            styles = getSampleStyleSheet()

            # Encabezados del PDF
            pdf.setFont("Helvetica-Bold", 9)
            y = 570
            pdf.drawString(50, y, f"Orden de Producción: {orden.numero_orden}")
            y -= 15
            pdf.drawString(50, y, f"Producto: {orden.producto_compuesto.codigo} - {orden.producto_compuesto.nombre}")
            y -= 15
            pdf.drawString(50, y, f"Cantidad de Paquetes: {orden.cantidad_paquetes}")
            y -= 15
            pdf.drawString(50, y, f"Bodega de Producción: {orden.bodega_produccion.nombre if orden.bodega_produccion else 'No especificada'}")
            y -= 15
            pdf.drawString(50, y, f"Estado: {orden.estado}")
            y -= 15
            pdf.drawString(50, y, f"Costo Unitario: ${orden.costo_unitario:.2f}  |  Costo Total: ${orden.costo_total:.2f}")
            y -= 15
            pdf.setFont("Helvetica", 8)
            pdf.drawString(50, y, f"Creado por: {nombre_creador}")
            y -= 15
            pdf.drawString(50, y, f"Producido por: {nombre_productor}")

            # Tabla de fechas
            y -= 15
            pdf.setFont("Helvetica-Bold", 8)
            pdf.drawString(50, y, "Fecha de Creación")
            pdf.drawString(200, y, "Fecha Lista para Producción")
            pdf.drawString(350, y, "Fecha Inicio Producción")
            pdf.drawString(500, y, "Fecha Finalización")
            y -= 12
            pdf.setFont("Helvetica", 7)
            pdf.drawString(50, y, orden.fecha_creacion.strftime('%Y-%m-%d %H:%M'))
            pdf.drawString(200, y, orden.fecha_lista_para_produccion.strftime('%Y-%m-%d %H:%M') if orden.fecha_lista_para_produccion else 'N/A')
            pdf.drawString(350, y, orden.fecha_inicio.strftime('%Y-%m-%d %H:%M') if orden.fecha_inicio else 'N/A')
            pdf.drawString(500, y, orden.fecha_finalizacion.strftime('%Y-%m-%d %H:%M') if orden.fecha_finalizacion else 'N/A')
            y -= 10
            pdf.line(50, y, 742, y)

            # Tabla de materiales
            y -= 15
            pdf.setFont("Helvetica-Bold", 10)
            pdf.drawString(50, y, "Detalle de la Orden")
            y -= 15
            pdf.setFont("Helvetica-Bold", 8)
            pdf.drawString(50, y, "Componente")
            pdf.drawString(250, y, "Cant. x Paquete")
            pdf.drawString(320, y, "Cant. Total")
            pdf.drawString(380, y, "Peso x Paquete")
            pdf.drawString(450, y, "Peso Total")
            pdf.drawString(520, y, "Costo Unitario")
            pdf.drawString(590, y, "Costo Total")
            y -= 15

            pdf.setFont("Helvetica", 7)

            def draw_wrapped_text(pdf, x, y, text, max_width):
                """Dibuja texto justificado que salta de línea si excede el ancho máximo."""
                words = text.split(" ")
                line = ""
                for word in words:
                    test_line = f"{line} {word}".strip()
                    if pdf.stringWidth(test_line, "Helvetica", 7) <= max_width:
                        line = test_line
                    else:
                        pdf.drawString(x, y, line)
                        y -= 8
                        line = word
                if line:
                    pdf.drawString(x, y, line)
                    y -= 8
                return y

            for material in materiales_producto:
                producto_base = db.session.get(Producto, material.producto_base_id)

                # Obtener costo unitario desde el último registro en kardex para la bodega de producción
                ultimo_kardex = db.session.query(Kardex).filter(
                    Kardex.producto_id == material.producto_base_id,
                    Kardex.bodega_destino_id == orden.bodega_produccion_id
                ).order_by(Kardex.fecha.desc()).first()
                costo_unitario = float(ultimo_kardex.saldo_costo_unitario) if ultimo_kardex else 0.0

                peso_x_paquete = float(material.cantidad * material.peso_unitario) if material.peso_unitario is not None else 0.0
                cantidad_total = float(material.cantidad) * orden.cantidad_paquetes
                peso_total = float(material.cantidad * material.peso_unitario * orden.cantidad_paquetes)
                costo_total = cantidad_total * costo_unitario

                y = draw_wrapped_text(pdf, 50, y, f"{producto_base.codigo} - {producto_base.nombre}", 200)
                pdf.drawString(250, y + 8, f"{material.cantidad:.2f}")
                pdf.drawString(320, y + 8, f"{cantidad_total:.2f}")
                pdf.drawString(380, y + 8, f"{peso_x_paquete:.2f}")
                pdf.drawString(450, y + 8, f"{peso_total:.2f}")
                pdf.drawString(520, y + 8, f"${costo_unitario:.2f}")
                pdf.drawString(590, y + 8, f"${costo_total:.2f}")
                y -= 8

                if y < 80:
                    pdf.showPage()
                    y = 550

            # Línea divisoria después de Detalle de la Orden
            y -= 10
            pdf.line(50, y, 742, y)

            # Tabla de historial de entregas
            y -= 15
            pdf.setFont("Helvetica-Bold", 10)
            pdf.drawString(50, y, "Historial de Entregas")
            y -= 15
            pdf.setFont("Helvetica-Bold", 8)
            pdf.drawString(50, y, "Fecha")
            pdf.drawString(200, y, "Cantidad Entregada")
            pdf.drawString(350, y, "Comentario")
            y -= 15

            pdf.setFont("Helvetica", 7)
            for entrega in entregas_parciales:
                pdf.drawString(50, y, entrega.fecha_entrega.strftime('%Y-%m-%d %H:%M'))
                pdf.drawString(200, y, str(entrega.cantidad_entregada))
                pdf.drawString(350, y, entrega.comentario or "N/A")
                y -= 10

                if y < 80:
                    pdf.showPage()
                    y = 550

            # Cantidad pendiente
            y -= 15
            pdf.setFont("Helvetica-Bold", 8)
            pdf.drawString(50, y, f"Cantidad Pendiente: {cantidad_pendiente}")

            # Línea divisoria después de Historial de Entregas
            y -= 10
            pdf.line(50, y, 742, y)

            # Mostrar "Cierre Forzado" o "Orden Finalizada sin Novedad" con título en negrita
            y -= 15
            pdf.setFont("Helvetica-Bold", 10)
            if tiene_cierre_forzado:
                pdf.drawString(50, y, "Cierre Forzado")
            elif orden.estado == "Finalizada":
                pdf.drawString(50, y, "Orden Finalizada sin Novedad")
            else:
                pdf.drawString(50, y, "Orden en Proceso de Producción")
            y -= 15

            # Mostrar el comentario (si lo hay) en texto normal
            if tiene_cierre_forzado:
                pdf.setFont("Helvetica", 8)
                y = draw_wrapped_text(pdf, 50, y, comentario_cierre_forzado, 700)

            # Agregar firmas al final en una fila horizontal
            if y < 80:
                pdf.showPage()
                y = 550

            pdf.setFont("Helvetica", 10)
            y -= 50

            # Despachado por (izquierda)
            pdf.line(50, y, 280, y)
            pdf.drawString(50, y - 12, "Despachado por")

            # Entregado por (centro)
            pdf.line(300, y, 530, y)
            pdf.drawString(300, y - 12, "Entregado por")

            # Recibido (derecha)
            pdf.line(550, y, 780, y)
            pdf.drawString(550, y - 12, "Recibido")

            # Finalizar y guardar el PDF
            pdf.save()
            buffer.seek(0)

            # Configurar la respuesta del PDF
            nombre_archivo = f"Orden_{orden.numero_orden}.pdf"
            response = make_response(buffer.getvalue())
            response.headers['Content-Type'] = 'application/pdf'
            response.headers['Content-Disposition'] = f'attachment; filename="{nombre_archivo}"'
            return response

        except Exception as e:
            print(f"Error al generar PDF: {str(e)}")
            return jsonify({'error': 'Ocurrió un error al generar el PDF'}), 500


    @app.route('/api/ordenes-produccion/<int:orden_id>/pdf-operador', methods=['GET'])
    def generar_pdf_orden_operador(orden_id):
        try:
            # Consultar la orden de producción
            orden = db.session.get(OrdenProduccion, orden_id)
            if not orden:
                return jsonify({'error': 'Orden de producción no encontrada'}), 404

            # Consultar el usuario creador
            usuario_creador = db.session.get(Usuario, orden.creado_por)
            nombre_creador = f"{usuario_creador.nombres} {usuario_creador.apellidos}" if usuario_creador else "Desconocido"

            # Consultar el usuario que produjo la orden
            usuario_productor = db.session.get(Usuario, orden.en_produccion_por)
            nombre_productor = f"{usuario_productor.nombres} {usuario_productor.apellidos}" if usuario_productor else "N/A"

            # Verificar si la orden tuvo un cierre forzado
            tiene_cierre_forzado = bool(orden.comentario_cierre_forzado)
            comentario_cierre_forzado = orden.comentario_cierre_forzado or "Orden finalizada sin novedad."

            # Consultar los materiales del producto compuesto
            materiales_producto = db.session.query(MaterialProducto).filter_by(
                producto_compuesto_id=orden.producto_compuesto_id
            ).all()

            # Consultar el historial de entregas y calcular cantidad pendiente
            entregas_parciales = db.session.query(EntregaParcial).filter_by(
                orden_produccion_id=orden_id
            ).all()
            entregas_totales = sum(entrega.cantidad_entregada for entrega in entregas_parciales)
            cantidad_pendiente = orden.cantidad_paquetes - entregas_totales

            # Configuración del PDF con orientación horizontal
            buffer = BytesIO()
            pdf = canvas.Canvas(buffer, pagesize=landscape(letter))

            # Encabezados del PDF
            pdf.setFont("Helvetica-Bold", 9)
            y = 570
            pdf.drawString(50, y, f"Orden de Producción: {orden.numero_orden}")
            y -= 15
            pdf.drawString(50, y, f"Producto: {orden.producto_compuesto.codigo} - {orden.producto_compuesto.nombre}")
            y -= 15
            pdf.drawString(50, y, f"Cantidad de Paquetes: {orden.cantidad_paquetes}")
            y -= 15
            pdf.drawString(50, y, f"Bodega de Producción: {orden.bodega_produccion.nombre if orden.bodega_produccion else 'No especificada'}")
            y -= 15
            pdf.drawString(50, y, f"Estado: {orden.estado}")
            y -= 15
            pdf.setFont("Helvetica", 8)
            pdf.drawString(50, y, f"Creado por: {nombre_creador}")
            y -= 15
            pdf.drawString(50, y, f"Producido por: {nombre_productor}")

            # Tabla de fechas
            y -= 15
            pdf.setFont("Helvetica-Bold", 8)
            pdf.drawString(50, y, "Fecha de Creación")
            pdf.drawString(200, y, "Fecha Lista para Producción")
            pdf.drawString(350, y, "Fecha Inicio Producción")
            pdf.drawString(500, y, "Fecha Finalización")
            y -= 12
            pdf.setFont("Helvetica", 7)
            pdf.drawString(50, y, orden.fecha_creacion.strftime('%Y-%m-%d %H:%M'))
            pdf.drawString(200, y, orden.fecha_lista_para_produccion.strftime('%Y-%m-%d %H:%M') if orden.fecha_lista_para_produccion else 'N/A')
            pdf.drawString(350, y, orden.fecha_inicio.strftime('%Y-%m-%d %H:%M') if orden.fecha_inicio else 'N/A')
            pdf.drawString(500, y, orden.fecha_finalizacion.strftime('%Y-%m-%d %H:%M') if orden.fecha_finalizacion else 'N/A')
            y -= 10
            pdf.line(50, y, 742, y)

            # Tabla de materiales (sin costos)
            y -= 15
            pdf.setFont("Helvetica-Bold", 10)
            pdf.drawString(50, y, "Detalle de la Orden")
            y -= 15
            pdf.setFont("Helvetica-Bold", 8)
            pdf.drawString(50, y, "Componente")
            pdf.drawString(400, y, "Cant. x Paquete")
            pdf.drawString(500, y, "Cant. Total")
            pdf.drawString(600, y, "Peso Total")
            y -= 15

            pdf.setFont("Helvetica", 7)

            def draw_wrapped_text(pdf, x, y, text, max_width):
                words = text.split(" ")
                line = ""
                for word in words:
                    test_line = f"{line} {word}".strip()
                    if pdf.stringWidth(test_line, "Helvetica", 7) <= max_width:
                        line = test_line
                    else:
                        pdf.drawString(x, y, line)
                        y -= 8
                        line = word
                if line:
                    pdf.drawString(x, y, line)
                    y -= 8
                return y

            for material in materiales_producto:
                producto_base = db.session.get(Producto, material.producto_base_id)
                peso_x_paquete = material.peso_unitario if material.peso_unitario is not None else (
                    producto_base.peso_unitario if producto_base and producto_base.peso_unitario is not None else 0
                )
                cantidad_total = material.cantidad * orden.cantidad_paquetes
                peso_total = cantidad_total * peso_x_paquete

                y = draw_wrapped_text(pdf, 50, y, f"{producto_base.codigo} - {producto_base.nombre}", 350)
                pdf.drawString(400, y + 8, f"{material.cantidad:.2f}")
                pdf.drawString(500, y + 8, f"{cantidad_total:.2f}")
                pdf.drawString(600, y + 8, f"{peso_total:.2f}")
                y -= 8

                if y < 80:
                    pdf.showPage()
                    y = 550

            # Línea divisoria después de Detalle de la Orden
            y -= 10
            pdf.line(50, y, 742, y)

            # Tabla de historial de entregas
            y -= 15
            pdf.setFont("Helvetica-Bold", 10)
            pdf.drawString(50, y, "Historial de Entregas")
            y -= 15
            pdf.setFont("Helvetica-Bold", 8)
            pdf.drawString(50, y, "Fecha")
            pdf.drawString(200, y, "Cantidad Entregada")
            pdf.drawString(350, y, "Comentario")
            y -= 15

            pdf.setFont("Helvetica", 7)
            for entrega in entregas_parciales:
                pdf.drawString(50, y, entrega.fecha_entrega.strftime('%Y-%m-%d %H:%M'))
                pdf.drawString(200, y, str(entrega.cantidad_entregada))
                pdf.drawString(350, y, entrega.comentario or "N/A")
                y -= 10

                if y < 80:
                    pdf.showPage()
                    y = 550

            # Cantidad pendiente
            y -= 15
            pdf.setFont("Helvetica-Bold", 8)
            pdf.drawString(50, y, f"Cantidad Pendiente: {cantidad_pendiente}")

            # Línea divisoria después de Historial de Entregas
            y -= 10
            pdf.line(50, y, 742, y)

            # Mostrar "Cierre Forzado" o "Orden Finalizada sin Novedad"
            # Mostrar "Cierre Forzado" o "Orden Finalizada sin Novedad" con título en negrita
            y -= 15
            pdf.setFont("Helvetica-Bold", 10)
            if tiene_cierre_forzado:
                pdf.drawString(50, y, "Cierre Forzado")
            elif orden.estado == "Finalizada":
                pdf.drawString(50, y, "Orden Finalizada sin Novedad")
            else:
                pdf.drawString(50, y, "Orden en Proceso de Producción")
            y -= 15

            if tiene_cierre_forzado:
                pdf.setFont("Helvetica", 8)
                y = draw_wrapped_text(pdf, 50, y, comentario_cierre_forzado, 700)

            # Agregar firmas al final
            if y < 80:
                pdf.showPage()
                y = 550

            pdf.setFont("Helvetica", 10)
            y -= 50
            pdf.line(50, y, 280, y)
            pdf.drawString(50, y - 12, "Despachado por")
            pdf.line(300, y, 530, y)
            pdf.drawString(300, y - 12, "Entregado por")
            pdf.line(550, y, 780, y)
            pdf.drawString(550, y - 12, "Recibido")

            # Finalizar y guardar el PDF
            pdf.save()
            buffer.seek(0)

            # Configurar la respuesta del PDF
            nombre_archivo = f"Orden_{orden.numero_orden}_Operador.pdf"
            response = make_response(buffer.getvalue())
            response.headers['Content-Type'] = 'application/pdf'
            response.headers['Content-Disposition'] = f'attachment; filename="{nombre_archivo}"'
            return response

        except Exception as e:
            print(f"Error al generar PDF para operador: {str(e)}")
            return jsonify({'error': 'Ocurrió un error al generar el PDF'}), 500



    # Geenerar PDF del listado de Ordenes de Producción:
    @app.route('/api/ordenes-produccion/listado-pdf', methods=['POST'])
    def generar_listado_pdf():
        try:
            data = request.get_json()
            estado = data.get('estado')
            fecha_inicio = data.get('fecha_inicio')
            fecha_fin = data.get('fecha_fin')

            # Consultar las órdenes con los filtros aplicados
            query = OrdenProduccion.query

            if estado:
                query = query.filter_by(estado=estado)
            if fecha_inicio and fecha_fin:
                query = query.filter(
                    OrdenProduccion.fecha_finalizacion.between(fecha_inicio, fecha_fin)
                )

            ordenes = query.all()

            # Crear el PDF
            buffer = BytesIO()
            pdf = canvas.Canvas(buffer, pagesize=landscape(letter))
            pdf.setFont("Helvetica-Bold", 14)
            pdf.drawString(30, 550, "Listado de Órdenes de Producción")

            # Encabezados
            pdf.setFont("Helvetica-Bold", 10)
            headers = ["# Orden", "Producto", "Cantidad", "Estado", "Fecha Estado", "Tiempo Producción"]
            x_positions = [30, 110, 380, 460, 550, 680]  # Se ajustaron las posiciones

            for i, header in enumerate(headers):
                pdf.drawString(x_positions[i], 520, header)

            # Función para ajustar texto
            def draw_wrapped_text(canvas, text, x, y, max_width, line_height):
                words = text.split(" ")
                line = ""
                for word in words:
                    test_line = f"{line} {word}".strip()
                    if canvas.stringWidth(test_line, "Helvetica", 10) <= max_width:
                        line = test_line
                    else:
                        canvas.drawString(x, y, line)
                        y -= line_height
                        line = word
                if line:
                    canvas.drawString(x, y, line)
                    y -= line_height
                return y


            def calcular_tiempo_produccion(orden):
                """Calcula el tiempo en producción en horas o días."""
                if not orden.fecha_creacion:
                    return "-"

                # Determinar la fecha de referencia según el estado de la orden
                fecha_referencia = (
                    orden.fecha_finalizacion if orden.estado == "Finalizada" else
                    orden.fecha_inicio if orden.estado in ["En Producción", "En Producción-Parcial"] else
                    orden.fecha_lista_para_produccion if orden.estado == "Lista para Producción" else
                    orden.fecha_creacion
                )

                if not fecha_referencia:
                    return "-"

                # Calcular la diferencia en horas
                if not fecha_referencia or not orden.fecha_creacion:
                    return "-"

                diferencia_horas = (fecha_referencia - orden.fecha_creacion).total_seconds() / 3600

                # Si el tiempo es mayor a 24 horas, mostrar en días
                if diferencia_horas >= 24:
                    return f"{int(diferencia_horas // 24)} día(s)"
                else:
                    return f"{int(diferencia_horas)} hora(s)"


            # Cuerpo del PDF
            pdf.setFont("Helvetica", 10)
            y = 500
            line_height = 15

            for orden in ordenes:
                producto_nombre = f"{orden.producto_compuesto.codigo} - {orden.producto_compuesto.nombre}"
                fecha_estado = (
                    orden.fecha_finalizacion or
                    orden.fecha_inicio or
                    orden.fecha_lista_para_produccion or
                    orden.fecha_creacion or "-"
                )

                # Datos a mostrar
                data = [
                    
                    orden.numero_orden,
                    producto_nombre,
                    str(orden.cantidad_paquetes),
                    orden.estado,
                    fecha_estado.strftime('%Y-%m-%d %H:%M') if fecha_estado else "-",
                    calcular_tiempo_produccion(orden)  # Nuevo cálculo
                ]

                y_position = y
                for i, value in enumerate(data):
                    if i == 1:  # Ajustar texto en la columna de Producto
                        y_position = draw_wrapped_text(
                            pdf, value, x_positions[i], y, max_width=250, line_height=line_height
                        )
                    else:
                        pdf.drawString(x_positions[i], y, value)

                y = y_position - line_height  # Ajustar espacio entre filas
                if y < 50:  # Salto de página si el contenido excede
                    pdf.showPage()
                    pdf.setFont("Helvetica", 10)
                    y = 550

            pdf.save()
            buffer.seek(0)

            response = make_response(buffer.getvalue())
            response.headers['Content-Type'] = 'application/pdf'
            response.headers['Content-Disposition'] = 'attachment; filename="Listado_Ordenes_Produccion.pdf"'
            return response

        except Exception as e:
            print(f"Error al generar listado PDF: {str(e)}")
            return jsonify({'error': 'Ocurrió un error al generar el listado PDF.'}), 500

    # Geenerar PDF del listado de Ordenes de Producción Operador:
    @app.route('/api/ordenes-produccion/listado-operador-pdf', methods=['POST'])
    def generar_listado_operador_pdf():
        try:
            data = request.get_json()
            estado = data.get('estado')
            fecha_inicio = data.get('fecha_inicio')
            fecha_fin = data.get('fecha_fin')

            # Consultar las órdenes con los filtros aplicados
            query = OrdenProduccion.query

            if estado:
                query = query.filter_by(estado=estado)
            if fecha_inicio and fecha_fin:
                query = query.filter(
                    OrdenProduccion.fecha_finalizacion.between(fecha_inicio, fecha_fin)
                )

            ordenes = query.all()

            # Crear el PDF
            buffer = BytesIO()
            pdf = canvas.Canvas(buffer, pagesize=landscape(letter))
            pdf.setFont("Helvetica-Bold", 14)
            pdf.drawString(30, 550, "Listado de Órdenes de Producción")

            # Encabezados
            pdf.setFont("Helvetica-Bold", 10)
            headers = ["# Orden", "Producto", "Cantidad", "Estado", "Fecha Estado"]
            x_positions = [30, 110, 440, 540, 650]

            for i, header in enumerate(headers):
                pdf.drawString(x_positions[i], 520, header)

            # Función para ajustar texto
            def draw_wrapped_text(canvas, text, x, y, max_width, line_height):
                words = text.split(" ")
                line = ""
                for word in words:
                    test_line = f"{line} {word}".strip()
                    if canvas.stringWidth(test_line, "Helvetica", 10) <= max_width:
                        line = test_line
                    else:
                        canvas.drawString(x, y, line)
                        y -= line_height
                        line = word
                if line:
                    canvas.drawString(x, y, line)
                    y -= line_height
                return y

            # Cuerpo del PDF
            pdf.setFont("Helvetica", 10)
            y = 500
            line_height = 15
            for orden in ordenes:
                producto_nombre = f"{orden.producto_compuesto.codigo} - {orden.producto_compuesto.nombre}"
                fecha_estado = (
                    orden.fecha_finalizacion if orden.estado == "Finalizada" else
                    orden.fecha_inicio if orden.estado in ["En Producción", "En Producción-Parcial"] else
                    orden.fecha_lista_para_produccion if orden.estado == "Lista para Producción" else
                    orden.fecha_creacion
                )

                # Datos a mostrar
                data = [
                    
                    orden.numero_orden,
                    producto_nombre,
                    str(orden.cantidad_paquetes),
                    orden.estado,
                    fecha_estado.strftime('%Y-%m-%d %H:%M') if fecha_estado else "-"
                ]

                y_position = y
                for i, value in enumerate(data):
                    if i == 1:  # Ajustar texto en la columna de Producto
                        y_position = draw_wrapped_text(
                            pdf, value, x_positions[i], y, max_width=300, line_height=line_height
                        )
                    else:
                        pdf.drawString(x_positions[i], y, value)

                y = y_position - line_height  # Ajustar espacio entre filas
                if y < 50:  # Salto de página si el contenido excede
                    pdf.showPage()
                    pdf.setFont("Helvetica", 10)
                    y = 550

            pdf.save()
            buffer.seek(0)

            response = make_response(buffer.getvalue())
            response.headers['Content-Type'] = 'application/pdf'
            response.headers['Content-Disposition'] = 'attachment; filename="Listado_Ordenes_Produccion.pdf"'
            return response

        except Exception as e:
            print(f"Error al generar listado PDF: {str(e)}")
            return jsonify({'error': 'Ocurrió un error al generar el listado PDF.'}), 500



    @app.route('/api/ordenes-produccion/operador', methods=['GET'])
    def obtener_ordenes_para_operador():
        try:
            # Consultar solo órdenes listas para producción
            ordenes = OrdenProduccion.query.filter_by(estado='Lista para Producción').all()
            resultado = [
                {
                    "id": orden.id,
                    "numero_orden": orden.numero_orden,
                    "producto_compuesto_id": orden.producto_compuesto_id,
                    "producto_compuesto_nombre": f"{orden.producto_compuesto.codigo} - {orden.producto_compuesto.nombre}",
                    "cantidad_paquetes": orden.cantidad_paquetes,
                    "estado": orden.estado,
                    "bodega_produccion_id": orden.bodega_produccion_id,
                    "bodega_produccion_nombre": orden.bodega_produccion.nombre,
                    "fecha_creacion": orden.fecha_creacion.isoformat(),
                }
                for orden in ordenes
            ]
            return jsonify(resultado), 200
        except Exception as e:
            print(f"Error al obtener órdenes para el operador: {str(e)}")
            return jsonify({'error': 'Ocurrió un error al obtener las órdenes para el operador.'}), 500


    @app.route('/api/ajuste-inventario', methods=['POST'])
    def ajuste_inventario():
        try:
            data = request.get_json()
            print("DEBUG: Datos recibidos en ajuste-inventario:", data)

            if 'bodega' not in data or 'productos' not in data or 'usuario_id' not in data:
                return jsonify({'error': 'Faltan datos en la solicitud (bodega, productos o usuario_id)'}), 400

            bodega = data['bodega']
            usuario_id = data['usuario_id']

            bodega_existente = Bodega.query.filter_by(nombre=bodega).first()
            if not bodega_existente:
                return jsonify({'error': 'Bodega no encontrada'}), 404

            usuario = db.session.get(Usuario, usuario_id)
            if not usuario:
                return jsonify({'error': 'Usuario no encontrado'}), 404

            consecutivo = generar_consecutivo()
            fecha_actual = obtener_hora_colombia()

            for producto_data in data['productos']:
                if not all(key in producto_data for key in ['codigoProducto', 'nuevaCantidad', 'tipoMovimiento']):
                    return jsonify({'error': 'Faltan datos en uno de los productos (código, cantidad, tipo)'}), 400

                codigo_producto = producto_data['codigoProducto']
                cantidad_ajuste = int(producto_data['nuevaCantidad'])
                tipo_movimiento = producto_data['tipoMovimiento']

                producto = Producto.query.filter_by(codigo=codigo_producto).first()
                if not producto:
                    return jsonify({'error': f'Producto {codigo_producto} no encontrado'}), 404

                estado_inventario = EstadoInventario.query.filter_by(
                    producto_id=producto.id, bodega_id=bodega_existente.id).first()

                if not estado_inventario:
                    if tipo_movimiento == "Disminuir":
                        return jsonify({'error': f'No hay inventario registrado para {codigo_producto} en la bodega'}), 404
                    estado_inventario = EstadoInventario(
                        producto_id=producto.id,
                        bodega_id=bodega_existente.id,
                        cantidad=0,
                        costo_unitario=Decimal('0.00'),
                        costo_total=Decimal('0.00'),
                        ultima_actualizacion=fecha_actual
                    )
                    db.session.add(estado_inventario)

                cantidad_anterior = estado_inventario.cantidad

                # Obtener el último registro del Kardex para esta bodega y producto
                ultimo_kardex = Kardex.query.filter(
                    Kardex.producto_id == producto.id,
                    (Kardex.bodega_origen_id == bodega_existente.id) | (Kardex.bodega_destino_id == bodega_existente.id)
                ).order_by(Kardex.fecha.desc()).first()

                print(f"DEBUG: Último Kardex encontrado: {ultimo_kardex}")

                # Determinar el costo unitario
                if tipo_movimiento == "Disminuir" and ultimo_kardex:
                    costo_unitario = ultimo_kardex.saldo_costo_unitario  # Usar el CPP del Kardex para salidas
                else:
                    costo_unitario = estado_inventario.costo_unitario or Decimal('0.00')  # Para entradas o si no hay Kardex

                costo_total = Decimal(str(cantidad_ajuste)) * costo_unitario

                # Saldos anteriores del Kardex
                saldo_cantidad_anterior = ultimo_kardex.saldo_cantidad if ultimo_kardex else Decimal('0')
                saldo_costo_total_anterior = ultimo_kardex.saldo_costo_total if ultimo_kardex else Decimal('0.00')
                saldo_costo_unitario_anterior = ultimo_kardex.saldo_costo_unitario if ultimo_kardex else Decimal('0.00')

                # Actualizar estado_inventario y calcular nuevos saldos
                if tipo_movimiento == "Incrementar":
                    valor_total_anterior = Decimal(str(cantidad_anterior)) * estado_inventario.costo_unitario
                    valor_total_nuevo = valor_total_anterior + costo_total
                    estado_inventario.cantidad += cantidad_ajuste
                    estado_inventario.costo_unitario = valor_total_nuevo / Decimal(str(estado_inventario.cantidad)) if estado_inventario.cantidad > 0 else Decimal('0.00')
                    estado_inventario.costo_total = valor_total_nuevo

                    saldo_cantidad = saldo_cantidad_anterior + Decimal(str(cantidad_ajuste))
                    saldo_costo_total = saldo_costo_total_anterior + costo_total
                    saldo_costo_unitario = saldo_costo_total / saldo_cantidad if saldo_cantidad > 0 else Decimal('0.00')
                elif tipo_movimiento == "Disminuir":
                    if estado_inventario.cantidad < cantidad_ajuste:
                        return jsonify({'error': f'No hay suficiente stock de {codigo_producto} para disminuir'}), 400
                    estado_inventario.cantidad -= cantidad_ajuste
                    estado_inventario.costo_unitario = costo_unitario  # Sincronizar con el CPP del Kardex
                    estado_inventario.costo_total = Decimal(str(estado_inventario.cantidad)) * estado_inventario.costo_unitario

                    saldo_cantidad = saldo_cantidad_anterior - Decimal(str(cantidad_ajuste))
                    saldo_costo_total = saldo_costo_total_anterior - costo_total
                    saldo_costo_unitario = saldo_costo_total / saldo_cantidad if saldo_cantidad > 0 else Decimal('0.00')

                estado_inventario.ultima_actualizacion = fecha_actual

                # Crear registro en RegistroMovimientos
                mensaje = f"Entrada por ajuste manual de inventario con consecutivo {consecutivo}" if tipo_movimiento == "Incrementar" \
                    else f"Salida por ajuste manual de inventario con consecutivo {consecutivo}"

                nuevo_movimiento = RegistroMovimientos(
                    consecutivo=consecutivo,
                    tipo_movimiento="ENTRADA" if tipo_movimiento == "Incrementar" else "SALIDA",
                    producto_id=producto.id,
                    bodega_origen_id=bodega_existente.id if tipo_movimiento == "Disminuir" else None,
                    bodega_destino_id=bodega_existente.id if tipo_movimiento == "Incrementar" else None,
                    cantidad=cantidad_ajuste,
                    fecha=fecha_actual,
                    descripcion=mensaje,
                    costo_unitario=costo_unitario,
                    costo_total=costo_total
                )
                db.session.add(nuevo_movimiento)

                # Crear registro en Kardex
                nuevo_kardex = Kardex(
                    producto_id=producto.id,
                    bodega_origen_id=bodega_existente.id if tipo_movimiento == "Disminuir" else None,
                    bodega_destino_id=bodega_existente.id if tipo_movimiento == "Incrementar" else None,
                    fecha=fecha_actual,
                    tipo_movimiento="ENTRADA" if tipo_movimiento == "Incrementar" else "SALIDA",
                    cantidad=Decimal(str(cantidad_ajuste)),
                    costo_unitario=costo_unitario,
                    costo_total=costo_total,
                    saldo_cantidad=saldo_cantidad,
                    saldo_costo_unitario=saldo_costo_unitario,
                    saldo_costo_total=saldo_costo_total,
                    referencia=f"Ajuste manual {consecutivo}"
                )
                db.session.add(nuevo_kardex)

                # Crear registro en AjusteInventarioDetalle
                nuevo_ajuste = AjusteInventarioDetalle(
                    consecutivo=consecutivo,
                    producto_id=producto.id,
                    producto_nombre=producto.nombre,
                    bodega_id=bodega_existente.id,
                    bodega_nombre=bodega_existente.nombre,
                    cantidad_anterior=cantidad_anterior,
                    tipo_movimiento=tipo_movimiento,
                    cantidad_ajustada=cantidad_ajuste,
                    cantidad_final=estado_inventario.cantidad,
                    fecha=fecha_actual,
                    usuario_id=usuario_id,
                    costo_unitario=costo_unitario,
                    costo_total=costo_total
                )
                db.session.add(nuevo_ajuste)

            db.session.commit()
            print(f"DEBUG: Ajuste realizado. Consecutivo: {consecutivo}")
            return jsonify({'message': 'Ajuste realizado con éxito', 'consecutivo': consecutivo}), 200

        except Exception as e:
            print(f"Error en ajuste de inventario: {e}")
            db.session.rollback()
            return jsonify({'error': 'Error al realizar el ajuste'}), 500

    @app.route('/api/consulta-ajustes', methods=['GET'])
    def consulta_ajustes():
        try:
            consecutivo = request.args.get('consecutivo')
            fecha_inicio = request.args.get('fechaInicio')
            fecha_fin = request.args.get('fechaFin')

            query = AjusteInventarioDetalle.query

            if consecutivo:
                query = query.filter(AjusteInventarioDetalle.consecutivo == consecutivo)
            elif fecha_inicio and fecha_fin:
                query = query.filter(AjusteInventarioDetalle.fecha.between(fecha_inicio, fecha_fin))

            ajustes = query.with_entities(
                AjusteInventarioDetalle.consecutivo,
                db.func.min(AjusteInventarioDetalle.fecha).label("fecha")
            ).group_by(AjusteInventarioDetalle.consecutivo).all()

            return jsonify([{"consecutivo": a.consecutivo, "fecha": a.fecha.strftime('%Y-%m-%d %H:%M:%S')} for a in ajustes])

        except Exception as e:
            print(f"Error en consulta de ajustes: {e}")
            return jsonify({'error': 'No se pudo recuperar la información'}), 500


    @app.route('/api/ajuste-detalle/<consecutivo>', methods=['GET'])
    def ajuste_detalle(consecutivo):
        try:
            detalles = (
                db.session.query(
                    AjusteInventarioDetalle,
                    Producto.codigo
                )
                .join(Producto, AjusteInventarioDetalle.producto_id == Producto.id)
                .filter(AjusteInventarioDetalle.consecutivo == consecutivo)
                .all()
            )

            return jsonify([
                {
                    "codigo_producto": producto_codigo,
                    "nombre_producto": d.producto_nombre,
                    "bodega_nombre": d.bodega_nombre,
                    "cantidad_anterior": d.cantidad_anterior,
                    "tipo_movimiento": d.tipo_movimiento,
                    "cantidad_ajustada": d.cantidad_ajustada,
                    "cantidad_final": d.cantidad_final,
                    "costo_unitario": float(d.costo_unitario) if d.costo_unitario is not None else 0.0,
                    "costo_total": float(d.costo_total) if d.costo_total is not None else 0.0
                } for d, producto_codigo in detalles
            ])

        except Exception as e:
            print(f"Error en consulta de detalle de ajuste: {e}")
            return jsonify({'error': 'No se pudo recuperar el detalle'}), 500


    @app.route('/api/ajuste-detalle-pdf/<consecutivo>', methods=['GET'])
    def generar_ajuste_pdf(consecutivo):
        try:
            # Obtener detalles del ajuste con LEFT JOIN para permitir usuario_id NULL
            detalles = (
                db.session.query(
                    AjusteInventarioDetalle,
                    Producto.codigo,
                    Usuario.nombres,
                    Usuario.apellidos
                )
                .join(Producto, AjusteInventarioDetalle.producto_id == Producto.id)
                .outerjoin(Usuario, AjusteInventarioDetalle.usuario_id == Usuario.id)
                .filter(AjusteInventarioDetalle.consecutivo == consecutivo)
                .all()
            )

            if not detalles:
                return jsonify({'error': 'Ajuste no encontrado'}), 404

            # Obtener fecha y usuario
            primer_detalle = detalles[0][0]
            fecha = primer_detalle.fecha.strftime('%Y-%m-%d %H:%M:%S')
            usuario_nombre = f"{detalles[0][2]} {detalles[0][3]}" if detalles[0][2] else "Desconocido"

            # Preparar datos para el PDF, incluyendo costo_unitario y costo_total
            detalles_json = [
                {
                    "codigo_producto": producto_codigo,
                    "nombre_producto": d.producto_nombre,
                    "bodega_nombre": d.bodega_nombre,
                    "cantidad_anterior": d.cantidad_anterior,
                    "tipo_movimiento": d.tipo_movimiento,
                    "cantidad_ajustada": d.cantidad_ajustada,
                    "cantidad_final": d.cantidad_final,
                    "costo_unitario": float(d.costo_unitario or 0),  # Nuevo
                    "costo_total": float(d.costo_total or 0)         # Nuevo
                } for d, producto_codigo, nombres, apellidos in detalles
            ]

            # Crear el PDF en formato horizontal
            buffer = BytesIO()
            pdf = canvas.Canvas(buffer, pagesize=landscape(letter))
            pdf.setTitle(f"Ajuste_{consecutivo}")

            # Encabezado
            pdf.setFont("Helvetica-Bold", 12)  # Reducido de 14 a 12
            pdf.drawString(30, 570, "Ajuste de Inventario")
            pdf.setFont("Helvetica", 10)  # Reducido de 12 a 10
            pdf.drawString(30, 550, f"Detalle del Ajuste {consecutivo}")
            pdf.drawString(30, 530, f"Fecha Realización: {fecha}")
            pdf.drawString(30, 510, f"Realizado por: {usuario_nombre}")
            pdf.line(30, 500, 780, 500)

            # Tabla
            pdf.setFont("Helvetica-Bold", 8)  # Reducido de 10 a 8
            y = 480
            # Ajustar posiciones para incluir nuevas columnas
            pdf.drawString(30, y, "Código")
            pdf.drawString(100, y, "Nombre Producto")
            pdf.drawString(300, y, "Bodega")
            pdf.drawString(360, y, "Cant. Anterior")
            pdf.drawString(430, y, "Acción")
            pdf.drawString(500, y, "Cant. Ajustada")
            pdf.drawString(570, y, "Cant. Final")
            pdf.drawString(640, y, "Costo Unit.")    # Nueva columna
            pdf.drawString(710, y, "Costo Total")    # Nueva columna
            pdf.line(30, y - 5, 780, y - 5)

            pdf.setFont("Helvetica", 8)  # Reducido de 10 a 8
            y -= 15  # Reducido de 20 a 15 para ahorrar espacio
            for detalle in detalles_json:
                if y < 80:  # Ajustado de 50 a 80 para dejar espacio a firmas
                    pdf.showPage()
                    pdf.setFont("Helvetica", 8)
                    y = 570
                    # Redibujar encabezados en nuevas páginas
                    pdf.setFont("Helvetica-Bold", 8)
                    pdf.drawString(30, y, "Código")
                    pdf.drawString(100, y, "Nombre Producto")
                    pdf.drawString(300, y, "Bodega")
                    pdf.drawString(360, y, "Cant. Anterior")
                    pdf.drawString(430, y, "Acción")
                    pdf.drawString(500, y, "Cant. Ajustada")
                    pdf.drawString(570, y, "Cant. Final")
                    pdf.drawString(640, y, "Costo Unit.")
                    pdf.drawString(710, y, "Costo Total")
                    pdf.line(30, y - 5, 780, y - 5)
                    pdf.setFont("Helvetica", 8)
                    y -= 15

                y_inicial = y
                max_width = 300 - 100  # Ancho reducido para Nombre Producto
                y_nueva = draw_wrapped_text_ajuste(pdf, 100, y_inicial, detalle["nombre_producto"], max_width)
                pdf.drawString(300, y_inicial, detalle["bodega_nombre"])
                pdf.drawString(360, y_inicial, str(detalle["cantidad_anterior"]))
                pdf.drawString(430, y_inicial, detalle["tipo_movimiento"])
                pdf.drawString(500, y_inicial, str(detalle["cantidad_ajustada"]))
                pdf.drawString(570, y_inicial, str(detalle["cantidad_final"]))
                pdf.drawString(640, y_inicial, f"${detalle['costo_unitario']:.2f}")  # Nueva columna
                pdf.drawString(710, y_inicial, f"${detalle['costo_total']:.2f}")     # Nueva columna
                y = min(y_inicial, y_nueva) - 15

            # Firmas al final
            pdf.setFont("Helvetica", 10)
            y_firmas = 60  # Más abajo en la hoja
            pdf.drawString(30, y_firmas, "Elaborado Por:")
            pdf.line(100, y_firmas + 5, 300, y_firmas + 5)  # Línea para firma
            pdf.drawString(400, y_firmas, "Aprobado Por:")
            pdf.line(470, y_firmas + 5, 670, y_firmas + 5)  # Línea para firma

            pdf.save()
            buffer.seek(0)
            return send_file(
                buffer,
                as_attachment=True,
                download_name=f"ajuste_{consecutivo}.pdf",
                mimetype="application/pdf"
            )
        except Exception as e:
            print(f"Error al generar PDF del ajuste: {str(e)}")
            return jsonify({'error': 'Ocurrió un error al generar el PDF.'}), 500


    @app.route('/api/consultaListado-ajustes-pdf', methods=['GET'])
    def generar_ajustes_pdf():
        try:
            fecha_inicio = request.args.get('fechaInicio')
            fecha_fin = request.args.get('fechaFin')

            if not fecha_inicio or not fecha_fin:
                return jsonify({'error': 'Faltan parámetros de fechas'}), 400

            query = AjusteInventarioDetalle.query
            query = query.filter(AjusteInventarioDetalle.fecha.between(fecha_inicio, fecha_fin))

            ajustes = query.with_entities(
                AjusteInventarioDetalle.consecutivo,
                db.func.min(AjusteInventarioDetalle.fecha).label("fecha")
            ).group_by(AjusteInventarioDetalle.consecutivo).all()

            if not ajustes:
                return jsonify({'error': 'No se encontraron ajustes en el rango de fechas'}), 404

            # Crear el PDF en formato vertical
            buffer = BytesIO()
            pdf = canvas.Canvas(buffer, pagesize=letter)  # Vertical por defecto
            pdf.setTitle(f"Ajustes_{fecha_inicio}_al_{fecha_fin}")

            # Encabezado
            pdf.setFont("Helvetica-Bold", 14)
            pdf.drawString(30, 750, "Ajustes de Inventario Realizados")
            pdf.setFont("Helvetica", 12)
            pdf.drawString(30, 730, f"Rango de fecha: {fecha_inicio} - {fecha_fin}")
            pdf.line(30, 720, 570, 720)

            # Tabla
            pdf.setFont("Helvetica-Bold", 10)
            y = 700
            pdf.drawString(30, y, "Consecutivo")
            pdf.drawString(200, y, "Fecha")
            pdf.line(30, y - 5, 570, y - 5)

            pdf.setFont("Helvetica", 10)
            y -= 20
            for ajuste in ajustes:
                if y < 50:  # Nueva página si no hay espacio
                    pdf.showPage()
                    pdf.setFont("Helvetica", 10)
                    y = 750
                    pdf.setFont("Helvetica-Bold", 10)
                    pdf.drawString(30, y, "Consecutivo")
                    pdf.drawString(200, y, "Fecha")
                    pdf.line(30, y - 5, 570, y - 5)
                    pdf.setFont("Helvetica", 10)
                    y -= 20

                pdf.drawString(30, y, ajuste.consecutivo)
                pdf.drawString(200, y, ajuste.fecha.strftime('%Y-%m-%d %H:%M:%S'))
                y -= 15

            pdf.save()
            buffer.seek(0)
            return send_file(
                buffer,
                as_attachment=True,
                download_name=f"Listado_ajustes_{fecha_inicio}_al_{fecha_fin}.pdf",
                mimetype="application/pdf"
            )
        except Exception as e:
            print(f"Error al generar PDF de ajustes: {str(e)}")
            return jsonify({'error': 'Ocurrió un error al generar el PDF.'}), 500

 
    @app.after_request
    def after_request(response):
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Authorization, Content-Type'
        return response


    # Rutas estáticas (prioridad baja)
    @app.route('/')
    def serve_frontend():
        return send_from_directory(app.static_folder, 'index.html')

    @app.route('/<path:path>', methods=['GET'])
    def serve_static(path):
        full_path = os.path.join(app.static_folder, path)
        if os.path.exists(full_path) and not path.startswith('api/'):
            return send_from_directory(app.static_folder, path)
        return send_from_directory(app.static_folder, 'index.html')

    @app.route('/debug-static')
    def debug_static():
        try:
            files = os.listdir(app.static_folder)
            return jsonify({'static_files': files, 'static_folder': app.static_folder})
        except Exception as e:
            return jsonify({'error': str(e), 'static_folder': app.static_folder})

    return app

# Crear la aplicación directamente en el nivel superior
app = create_app()

if __name__ == '__main__':
        
    with app.app_context():
        db.create_all()  # Crea las tablas si no existen
    port = int(os.getenv('PORT', 5000))  # Usa $PORT si existe (Railway), o 5000 por defecto
    app.run(debug=True, host='0.0.0.0', port=port)
