from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
from datetime import datetime, timedelta

db = SQLAlchemy()

# Manejo de sesion activa
class SesionActiva(db.Model):
    __tablename__ = 'sesiones_activas'

    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    token = db.Column(db.String(255), unique=True, nullable=False)
    ultima_actividad = db.Column(db.DateTime, nullable=False)  # Se configurará manualmente en los endpoints
    fecha_expiracion = db.Column(db.DateTime, nullable=False)  # Se configurará manualmente en los endpoints

    usuario = db.relationship('Usuario', backref='sesiones')

# Modelo Producto
class Producto(db.Model):
    __tablename__ = 'productos'
    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(20), unique=True, nullable=False)
    nombre = db.Column(db.String(255), nullable=False)
    peso_total_gr = db.Column(db.Numeric(10,2))  # Cambiado a Numeric
    peso_unidad_gr = db.Column(db.Numeric(10,2))  # Cambiado a Numeric
    codigo_barras = db.Column(db.String(50))
    es_producto_compuesto = db.Column(db.Boolean, default=False)
    peso_unitario_calculado = db.Column(db.Numeric)
    stock_minimo = db.Column(db.Integer, nullable=True)  # Nuevo campo agregado

    # Relación con materiales_producto como producto compuesto
    materiales_compuestos = db.relationship(
        'MaterialProducto',
        foreign_keys='MaterialProducto.producto_compuesto_id',
        backref='producto_compuesto',
        cascade='all, delete-orphan'
    )

    # Relación con materiales_producto como producto base
    materiales_bases = db.relationship(
        'MaterialProducto',
        foreign_keys='MaterialProducto.producto_base_id',
        backref='producto_base',
        cascade='all, delete-orphan'
    )

    def __repr__(self):
        return f"<Producto(id={self.id}, nombre='{self.nombre}', codigo='{self.codigo}')>"


# Modelo MaterialProducto
class MaterialProducto(db.Model):
    __tablename__ = 'materiales_producto'
    id = db.Column(db.Integer, primary_key=True)
    producto_compuesto_id = db.Column(
        db.Integer,
        db.ForeignKey('productos.id', ondelete='CASCADE'),
        nullable=False
    )
    producto_base_id = db.Column(
        db.Integer,
        db.ForeignKey('productos.id', ondelete='CASCADE'),
        nullable=False
    )
    cantidad = db.Column(db.Numeric(10,2), nullable=False)
    peso_unitario = db.Column(db.Numeric(10,2), nullable=False)
    
# Modelo Bodega
class Bodega(db.Model):
    __tablename__ = 'bodegas'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(255), nullable=False)

# Modelo Movimiento
class Movimiento(db.Model):
    __tablename__ = 'movimientos'
    id = db.Column(db.Integer, primary_key=True)
    tipo_movimiento = db.Column(db.String(10), nullable=False)
    producto_id = db.Column(db.Integer, db.ForeignKey('productos.id'))
    bodega_origen_id = db.Column(db.Integer, db.ForeignKey('bodegas.id'))
    bodega_destino_id = db.Column(db.Integer, db.ForeignKey('bodegas.id'))
    cantidad = db.Column(db.Integer, nullable=False)
    fecha = db.Column(db.DateTime, nullable=False)
    consecutivo = db.Column(db.String(20), nullable=False)

# Modelo InventarioBodega
class InventarioBodega(db.Model):
    __tablename__ = 'inventario_bodega'
    id = db.Column(db.Integer, primary_key=True)
    producto_id = db.Column(db.Integer, db.ForeignKey('productos.id'), nullable=False)
    bodega_id = db.Column(db.Integer, db.ForeignKey('bodegas.id'), nullable=False)
    cantidad = db.Column(db.Integer, nullable=False, default=0)
    factura = db.Column(db.String(50))
    contenedor = db.Column(db.String(50))
    fecha_ingreso = db.Column(db.DateTime, nullable=False)
    orden_produccion_id = db.Column(db.Integer, db.ForeignKey('ordenes_produccion.id'))
    costo_unitario = db.Column(db.Numeric(15, 2), default=0.00)  # Nuevo
    costo_total = db.Column(db.Numeric(15, 2), default=0.00)     # Nuevo


# Modelo OrdenProduccion
class OrdenProduccion(db.Model):
    __tablename__ = 'ordenes_produccion'

    id = db.Column(db.Integer, primary_key=True)
    producto_compuesto_id = db.Column(db.Integer, db.ForeignKey('productos.id'), nullable=False)
    cantidad_paquetes = db.Column(db.Integer, nullable=False)
    peso_total = db.Column(db.Numeric(10, 2))
    estado = db.Column(db.String(50), nullable=False, default='Pendiente')
    bodega_produccion_id = db.Column(db.Integer, db.ForeignKey('bodegas.id'), nullable=False)
    fecha_creacion = db.Column(db.DateTime, nullable=False)
    fecha_inicio = db.Column(db.DateTime)  # Representa el inicio de la producción
    fecha_finalizacion = db.Column(db.DateTime)  # Representa la finalización de la producción
    fecha_lista_para_produccion = db.Column(db.DateTime)  # Representa el cambio a "Lista para Producción"
    creado_por = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    numero_orden = db.Column(db.String(20), unique=True, nullable=False)
    en_produccion_por = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True)
    comentario_cierre_forzado = db.Column(db.Text)
    costo_unitario = db.Column(db.Float, nullable=True)  # Nuevo campo para el costo unitario del producto compuesto
    costo_total = db.Column(db.Float, nullable=True)     # Nuevo campo para el costo total de la orden

    # Relaciones
    producto_compuesto = db.relationship('Producto', backref='ordenes_produccion')
    bodega_produccion = db.relationship('Bodega', backref='ordenes_produccion')
    creado_por_usuario = db.relationship('Usuario', foreign_keys=[creado_por], backref='ordenes_creadas')
    en_produccion_usuario = db.relationship('Usuario', foreign_keys=[en_produccion_por], backref='ordenes_en_produccion')

    def __repr__(self):
        return f"<OrdenProduccion(id={self.id}, estado='{self.estado}', numero_orden='{self.numero_orden}')>"


# Modelo DetalleProduccion
class DetalleProduccion(db.Model):
    __tablename__ = 'detalle_produccion'
    id = db.Column(db.Integer, primary_key=True)
    orden_produccion_id = db.Column(db.Integer, db.ForeignKey('ordenes_produccion.id'), nullable=False)
    producto_base_id = db.Column(db.Integer, db.ForeignKey('productos.id'), nullable=False)
    cantidad_consumida = db.Column(db.Integer, nullable=False)
    cantidad_producida = db.Column(db.Integer, nullable=False)
    bodega_destino_id = db.Column(db.Integer, db.ForeignKey('bodegas.id'), nullable=False)
    fecha_registro = db.Column(db.DateTime, nullable=False)

    # Relaciones
    orden_produccion = db.relationship('OrdenProduccion', backref='detalle_produccion')
    producto_base = db.relationship('Producto', backref='detalle_produccion')
    bodega_destino = db.relationship('Bodega', backref='detalle_produccion')

# Modelo Venta
class Venta(db.Model):
    __tablename__ = 'ventas'
    id = db.Column(db.Integer, primary_key=True)
    factura = db.Column(db.String(50), nullable=False)
    producto_id = db.Column(db.Integer, db.ForeignKey('productos.id'))
    nombre_producto = db.Column(db.String(100))
    cantidad = db.Column(db.Integer, nullable=False)
    fecha_venta = db.Column(db.DateTime, nullable=False)
    bodega_id = db.Column(db.Integer, db.ForeignKey('bodegas.id'), nullable=False)
    precio_unitario = db.Column(db.Float, nullable=True)  # Nuevo campo opcional

    # Relaciones opcionales (si las necesitas)
    producto = db.relationship('Producto', backref='ventas')
    bodega = db.relationship('Bodega', backref='ventas')
    
# Modelo EstadoInventario
class EstadoInventario(db.Model):
    __tablename__ = 'estado_inventario'
    id = db.Column(db.Integer, primary_key=True)
    producto_id = db.Column(db.Integer, db.ForeignKey('productos.id'), nullable=False)
    bodega_id = db.Column(db.Integer, db.ForeignKey('bodegas.id'), nullable=False)
    cantidad = db.Column(db.Integer, nullable=False, default=0)
    ultima_actualizacion = db.Column(db.DateTime, nullable=False, onupdate=db.func.now())
    costo_unitario = db.Column(db.Numeric(15, 2), default=0.00)  # Nuevo
    costo_total = db.Column(db.Numeric(15, 2), default=0.00)     # Nuevo

    # Relaciones
    producto = db.relationship('Producto', backref='estado_inventario')
    bodega = db.relationship('Bodega', backref='estado_inventario')

# Modelo RegistroMovimientos
class RegistroMovimientos(db.Model):
    __tablename__ = 'registro_movimientos'
    id = db.Column(db.Integer, primary_key=True)
    consecutivo = db.Column(db.String(20), nullable=False)
    tipo_movimiento = db.Column(db.String(50), nullable=False)
    producto_id = db.Column(db.Integer, db.ForeignKey('productos.id'))
    bodega_origen_id = db.Column(db.Integer, db.ForeignKey('bodegas.id'))
    bodega_destino_id = db.Column(db.Integer, db.ForeignKey('bodegas.id'))
    cantidad = db.Column(db.Integer, nullable=False)
    fecha = db.Column(db.DateTime, nullable=False)
    descripcion = db.Column(db.Text)
    costo_unitario = db.Column(db.Numeric(15, 2), default=0.00)  # Nuevo
    costo_total = db.Column(db.Numeric(15, 2), default=0.00)     # Nuevo

    # Relaciones
    producto = db.relationship('Producto', backref='movimientos')
    bodega_origen = db.relationship('Bodega', foreign_keys=[bodega_origen_id])
    bodega_destino = db.relationship('Bodega', foreign_keys=[bodega_destino_id])

# Modelo Usuario
class Usuario(db.Model):
    __tablename__ = 'usuarios'

    id = db.Column(db.Integer, primary_key=True)
    usuario = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    nombres = db.Column(db.String(100), nullable=False)
    apellidos = db.Column(db.String(100), nullable=False)
    correo = db.Column(db.String(100))
    celular = db.Column(db.String(20))
    tipo_usuario = db.Column(db.String(50), nullable=False)
    activo = db.Column(db.Boolean, default=True)
    fecha_creacion = db.Column(db.DateTime, nullable=False)
    bodega_asignada = db.Column(db.Integer, db.ForeignKey('bodegas.id'))

    def __repr__(self):
        return f"<Usuario(id={self.id}, usuario='{self.usuario}', activo={self.activo})>"

class EntregaParcial(db.Model):
    __tablename__ = 'entregas_parciales'

    id = db.Column(db.Integer, primary_key=True)
    orden_produccion_id = db.Column(db.Integer, db.ForeignKey('ordenes_produccion.id'), nullable=False)
    cantidad_entregada = db.Column(db.Integer, nullable=False)
    fecha_entrega = db.Column(db.DateTime, nullable=False)  # Se configurará manualmente en los endpoints
    comentario = db.Column(db.Text, nullable=True)

    # Relación con OrdenProducción
    orden = db.relationship('OrdenProduccion', backref=db.backref('entregas_parciales', lazy='dynamic'))

    def __repr__(self):
        return (
            f"<EntregaParcial(id={self.id}, orden_produccion_id={self.orden_produccion_id}, "
            f"cantidad_entregada={self.cantidad_entregada}, fecha_entrega={self.fecha_entrega})>"
        )
    

class AjusteInventarioDetalle(db.Model):
    __tablename__ = 'ajuste_inventario_detalle'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    consecutivo = db.Column(db.String(20), nullable=False, index=True)
    producto_id = db.Column(db.Integer, db.ForeignKey('productos.id'), nullable=False)
    producto_nombre = db.Column(db.String(255), nullable=False)
    bodega_id = db.Column(db.Integer, db.ForeignKey('bodegas.id'), nullable=False)
    bodega_nombre = db.Column(db.String(255), nullable=False)
    cantidad_anterior = db.Column(db.Integer, nullable=False)
    tipo_movimiento = db.Column(db.String(20), nullable=False)  # Incrementar o Disminuir
    cantidad_ajustada = db.Column(db.Integer, nullable=False)
    cantidad_final = db.Column(db.Integer, nullable=False)
    fecha = db.Column(db.DateTime, nullable=False)  # Formato UTC con obtener_hora_utc()
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True)  # Nuevo campo
    costo_unitario = db.Column(db.Numeric(15, 2), default=0.00)  # Nuevo
    costo_total = db.Column(db.Numeric(15, 2), default=0.00)     # Nuevo

    def __repr__(self):
        return f"<AjusteInventarioDetalle {self.consecutivo} - {self.producto_nombre}>"


class Kardex(db.Model):
    __tablename__ = 'kardex'
    id = db.Column(db.Integer, primary_key=True)
    producto_id = db.Column(db.Integer, db.ForeignKey('productos.id'), nullable=False)
    bodega_origen_id = db.Column(db.Integer, db.ForeignKey('bodegas.id'), nullable=True)
    bodega_destino_id = db.Column(db.Integer, db.ForeignKey('bodegas.id'), nullable=True)
    fecha = db.Column(db.DateTime, nullable=False)
    tipo_movimiento = db.Column(db.String(50), nullable=False)
    cantidad = db.Column(db.Numeric(15, 3), nullable=False)
    costo_unitario = db.Column(db.Numeric(15, 2), default=0.00)
    costo_total = db.Column(db.Numeric(15, 2), default=0.00)
    saldo_cantidad = db.Column(db.Numeric(15, 3), nullable=False)
    saldo_costo_unitario = db.Column(db.Numeric(15, 2), default=0.00)
    saldo_costo_total = db.Column(db.Numeric(15, 2), default=0.00)
    referencia = db.Column(db.String(100))

    producto = db.relationship('Producto', backref='kardex_entries')
    bodega_origen = db.relationship('Bodega', foreign_keys=[bodega_origen_id], backref='kardex_origen_entries')
    bodega_destino = db.relationship('Bodega', foreign_keys=[bodega_destino_id], backref='kardex_destino_entries')
