<template>
    
  <h1>Gestión de Productos y Materiales</h1>
  
  <div>
    <button @click="volverAlMenu" class="btn btn-secondary">Volver al Menú</button>
    <button @click="limpiarPagina" class="btn btn-warning">Limpiar Página</button>
  </div>

  <!-- Subida de Archivo CSV -->
  <section class="carga-csv">
    <h2>Carga Masiva de Productos desde archivo .CSV</h2>

    <!-- Indicador de carga -->
      <div v-if="isLoadingCarga" class="spinner-container">
          <div class="spinner"></div>
          <p>Procesando archivo CSV, por favor espera...</p>
      </div>

      <!-- Input para subir archivo -->
      <div class="carga-input">
          <input type="file" @change="cargarCsv" ref="inputCsv" />
          <button @click="procesarCsv" :disabled="isLoadingCarga">Subir</button>
          <button @click="limpiarSesionCsv" :disabled="isLoadingCarga" class="btn-warning">Limpiar Sesión</button>
      </div>

    <!-- Mostrar errores en un área de texto copiable -->
    <div v-if="erroresCsv" class="error-container">
        <h3>Errores Detectados</h3>
        <textarea readonly v-model="erroresCsv"></textarea>
        <button @click="copiarErrores">Copiar errores</button>
    </div>

    <!-- Modal para el instructivo de uso -->
    <div v-if="mostrarModal" class="modal-instructivo">
        <div class="modal-contenido">
            <h3>📄 Instructivo de Uso para Carga de Productos</h3>
            <p>1️⃣ **Código**: Código único del producto. No debe repetirse.</p>
            <p>2️⃣ **Nombre**: Nombre del producto.</p>
            <p>3️⃣ **Peso Total / Unidad**: Obligatorio solo para productos Base.</p>
            <p>4️⃣ **Código de Barras**: Código de barras opcional.</p>
            <p>5️⃣ **Es Producto Compuesto**: "Sí" si el producto es compuesto, "No" si es producto Base.</p>
            <p>6️⃣ **Stock Mínimo**: Cantidad mínima de inventario (opcional, número entero o decimal).</p>
            <p>7️⃣ **Cantidad Productos**: Si el producto es Base, se coloca 0. Si es compuesto, indicar cuántos productos lo conforman.</p>
            <p>8️⃣ **Código y Cantidad de Productos compuestos**: Se deben indicar los códigos y cantidades de los productos compuestos.</p>
            <button @click="cerrarModal" class="btn-cerrar">Cerrar</button>
        </div>
    </div>
</section>

 <!-- Nueva sección: Actualización masiva de productos -->
  <!-- Sección: Actualización Masiva de Productos -->
  <section class="carga-csv">
    <h2>Actualización Masiva de Productos desde archivo .CSV</h2>

    <!-- Indicador de carga -->
      <div v-if="isLoadingActualizar" class="spinner-container">
          <div class="spinner"></div>
          <p>Procesando archivo CSV de actualización, por favor espera...</p>
      </div>

      <!-- Input para subir archivo -->
      <div class="carga-input">
          <input type="file" accept=".csv" @change="cargarArchivoActualizarCsv" ref="inputActualizarCsv" />
          <button @click="procesarActualizacionCsv" :disabled="!archivoActualizarCsv || isLoadingActualizar">Subir</button>
          <button @click="limpiarActualizarCsv" :disabled="!archivoActualizarCsv || isLoadingActualizar" class="btn-warning">Limpiar Sesión</button>
      </div>

    <!-- Enlaces para descargar la plantilla e instructivo -->
    <div class="carga-links">
      <a @click="descargarPlantillaActualizarCSV" class="link-descarga">📥 Descargar Plantilla CSV</a>
      <a @click="mostrarInstructivoActualizar" class="link-instructivo">📖 Instructivo de Uso</a>
    </div>

    <!-- Mostrar errores en un área de texto copiable -->
    <div v-if="erroresActualizarCsv" class="error-container">
      <h3>Errores Detectados</h3>
      <textarea readonly v-model="erroresActualizarCsv"></textarea>
      <button @click="copiarErroresActualizar">Copiar errores</button>
    </div>

    <!-- Modal para el instructivo de actualización -->
    <div v-if="mostrarModalActualizar" class="modal-instructivo">
      <div class="modal-contenido">
        <h3>📄 Instructivo para Actualizar Productos desde CSV</h3>
        <p>1️⃣ **Código**: Código del producto existente (obligatorio).</p>
        <p>2️⃣ **Nombre**: Nuevo nombre del producto (debe ser único).</p>
        <p>3️⃣ **Peso Total (gr)**: Peso total para productos base.</p>
        <p>4️⃣ **Peso Unidad (gr)**: Peso por unidad para productos base.</p>
        <p>5️⃣ **Código de Barras**: Código de barras (opcional).</p>
        <p>6️⃣ **Es Producto Compuesto**: "Sí" o "No".</p>
        <p>7️⃣ **Stock Mínimo**: Número entero o vacío (opcional).</p>
        <p>8️⃣ **Cantidad Productos**: Número de productos base para compuestos.</p>
        <p>9️⃣ **Código1, Cantidad1, etc.**: Materiales para productos compuestos.</p>
        <p>📝 **Notas**:</p>
        <p>- Los campos vacíos no modificarán los valores existentes.</p>
        <p>- Los productos base deben existir.</p>
        <p>- El nombre debe ser único en el sistema.</p>
        <button @click="cerrarModalActualizar" class="btn-cerrar">Cerrar</button>
      </div>
    </div>
  </section>


  <!-- Formulario para Crear/Editar Producto -->
  <section>
    <h2>Crear o Editar Producto</h2>
    <form @submit.prevent="modoEdicion ? actualizarProducto() : crearProducto()">
        <div>
            <label for="codigo">Código del Producto:</label>
            <input v-model="producto.codigo" id="codigo" required :disabled="modoEdicion" />
        </div>
        <div>
            <label for="nombre">Nombre del Producto:</label>
            <input v-model="producto.nombre" id="nombre" required />
        </div>
        <div>
            <label for="codigo_barras">Código de Barras:</label>
            <input v-model="producto.codigo_barras" id="codigo_barras" />
        </div>
        <div>
        <label>Tipo de Producto:</label>
            <select v-model="producto.es_producto_compuesto">
                <option :value="false">Base</option>
                <option :value="true">Compuesto</option>
            </select>
        </div>
        <div>
            <label for="peso_total">Peso Total en Gramos:</label>
            <input v-model.number="producto.peso_total_gr" id="peso_total" type="number" step="0.01"
                :required="!producto.es_producto_compuesto" 
                :disabled="producto.es_producto_compuesto" />
        </div>
        <div>
            <label for="peso_unidad">Peso por Unidad en Gramos:</label>
            <input v-model.number="producto.peso_unidad_gr" id="peso_unidad" type="number" step="0.01"
                :required="!producto.es_producto_compuesto" 
                :disabled="producto.es_producto_compuesto" />
        </div>
        <div>
            <label for="stock_minimo">Stock Mínimo:</label>
            <input v-model.number="producto.stock_minimo" id="stock_minimo" type="number" min="0" />
        </div>

        <div>
            <button v-if="!modoEdicion" type="submit">Crear Producto</button>
            <div v-else>
            <button type="submit">Guardar Producto</button>
            <button type="button" @click="cancelarEdicion">Cancelar</button>
            <button type="button" @click="limpiarSesion" class="btn-limpiar">Limpiar Sesión</button>
            </div>
        </div>
    
    </form>
  </section>

  <!-- Formulario para Definir Materiales de un Producto Compuesto -->
  <section v-if="producto.es_producto_compuesto && producto.id">
    <h3>Materiales del Producto</h3>

    <table>
        <thead>
        <tr>
            <th>Producto Base</th>
            <th>Cantidad</th>
            <th>Peso Unitario (g)</th>
            <th>Peso Total (g)</th>
            <th>Acciones</th>
        </tr>
        </thead>
        <tbody>
            <tr v-for="(material, index) in materiales" :key="material.id">
                <td>
                    <input type="text" v-model="material.nombreDigitado" placeholder="Buscar por nombre" @input="sincronizarPorNombre(index)" />
                    <select v-model="material.producto_base" @change="sincronizarCodigo(index)">
                        <option :value="null" disabled>Seleccione un producto</option>
                        <option v-for="prod in productosDisponibles" :key="prod.id" :value="prod.id">
                            {{ prod.codigo }} - {{ prod.nombre }}
                        </option>
                    </select>
                    <input type="text" v-model="material.codigoDigitado" placeholder="Ingrese código del material" @input="sincronizarSelector(index)" />
                </td>
                <td>
                    <input v-model.number="material.cantidad" type="number" step="0.01" min="0.01" required @input="actualizarPesoMaterial(index)" />
                </td>
                <td>{{ material.peso_unitario }}</td>
                <td>{{ material.peso_total }}</td>
                <td>
                    <button @click.prevent="eliminarMaterial(index)">Eliminar</button>
                </td>
            </tr>
        </tbody>
    </table>

    <button @click.prevent="agregarMaterial">Agregar Material</button>
    <button @click.prevent="guardarMateriales">Guardar Materiales</button>
  </section>


<!-- Consulta de Productos -->
<section class="consulta-productos">
    <h2>Consulta de Productos Creados</h2>

    <!-- Filtros de búsqueda -->
    <div class="filtros">
        <div class="filtro-item">
            <label for="buscarCodigo">Buscar por Código:</label>
            <input v-model="filtroCodigo" id="buscarCodigo" placeholder="Ingrese código de producto" />
        </div>
        <div class="filtro-item">
            <label for="buscarNombre">Buscar por Nombre:</label>
            <input v-model="filtroNombre" id="buscarNombre" placeholder="Ingrese nombre o parte del nombre" />
        </div>
        <div class="filtro-item">
            <label for="limit">Mostrar:</label>
            <select v-model="limit" id="limit" @change="consultarProductos">
                <option value="10">10</option>
                <option value="20">20</option>
                <option value="50">50</option>
                <option value="100">100</option>
                <option value="0">Todos</option>
            </select>
            <span> productos</span>
        </div>
        <!-- Botones de acción -->
        <div class="filtro-boton">
            <button @click="consultarProductos">Consultar Productos</button>
            <button @click="limpiarCampos" class="btn-limpiar">Limpiar Campos</button> <!-- Nuevo botón -->
        </div>
    </div>

    <!-- Lista de Productos -->
    <div v-if="productos.length">
        <h2>Productos Cargados</h2>
        <button @click="exportarAExcel" class="btn">Exportar a Excel</button> <!-- Nuevo botón -->
        <div class="tabla-container">
            <table>
                <thead>
                    <tr>
                        <th>Código</th>
                        <th>Nombre</th>
                        <th>Peso Total (g)</th>
                        <th>Peso Unidad (g)</th>
                        <th>Código de Barras</th>
                        <th>Prod. Compuesto</th>
                        <th>Stock Mínimo</th> <!-- Nueva columna -->
                        <th>Acciones</th>
                    </tr>
                </thead>
                <tbody>
                    <tr v-for="prod in productos" :key="prod.id">
                        <td>{{ prod.codigo }}</td>
                        <td>{{ prod.nombre }}</td>
                        <td>{{ prod.peso_total_gr }}</td>
                        <td>{{ prod.peso_unidad_gr }}</td>
                        <td>{{ prod.codigo_barras }}</td>
                        <td>{{ prod.es_producto_compuesto ? 'Sí' : 'No' }}</td>
                        <td>{{ prod.stock_minimo !== null ? prod.stock_minimo : '-' }}</td> <!-- Mostrar valor o '-' -->
                        <td>
                            <button @click="editarProducto(prod)">Editar</button>
                            <button @click="eliminarProducto(prod.id)">Eliminar</button>
                        </td>
                    </tr>
                </tbody>
            </table>
        </div>

        <button v-if="productos.length < totalProductos" @click="cargarMasProductos">
            Cargar más productos
        </button>
    </div>
</section>



</template>

<script>
import apiClient from '../services/axios';
import * as XLSX from 'xlsx';

export default {
name: 'GestionProductosMateriales',
data() {
  return {
    producto: { id: null, codigo: '', nombre: '', es_producto_compuesto: false, stock_minimo: null }, // Añadido stock_minimo por defecto
    productos: [],
    materiales: [],
    productosDisponibles: [],
    modoEdicion: false,
    filtroCodigo: '',
    filtroNombre: '',
    totalProductos: 0,
    offset: 0,
    limit: 50, // Valor por defecto
    archivoCsv: null,
    archivoActualizarCsv: null,
    erroresCsv: '',
    erroresActualizarCsv: '',
    mostrarModal: false,
    mostrarModalActualizar: false,
    isLoadingCarga: false, // Para Carga Masiva
    isLoadingActualizar: false // Para Actualización Masiva
  };
},
methods: {
    async crearProducto() {
        try {
            // Si el producto es compuesto, eliminamos los campos de peso
            if (this.producto.es_producto_compuesto) {
                delete this.producto.peso_total_gr;
                delete this.producto.peso_unidad_gr;
            }

            const response = await apiClient.post('/api/gestion-productos-materiales', this.producto);
            this.producto.id = response.data.id;
            alert('Producto creado correctamente');
            this.resetearFormulario();
            this.consultarProductos();
        } catch (error) {
            if (error.response && error.response.status === 400) {
                alert(error.response.data.error);
            } else {
                console.error('Error al crear producto:', error);
            }
        }
    },
    async consultarProductos() {
        try {
            // Si el usuario selecciona "Todos", enviar un valor grande en lugar de 0
            const limiteConsulta = this.limit === 0 ? 10000 : this.limit;

            const params = {
                offset: this.offset,
                limit: limiteConsulta,
                search_codigo: this.filtroCodigo || '',
                search_nombre: this.filtroNombre || ''
            };

            const response = await apiClient.get('/api/productos', { params });

            if (response.data.productos.length === 0) {
                alert("Código de Producto no encontrado. Intente con otro código.");
                return;
            }

            // No reiniciar la tabla, solo actualizar la data. Ordenar los porductos por codigo en orden ascendente
            this.productos = response.data.productos.sort((a, b) => a.codigo.localeCompare(b.codigo));
            this.totalProductos = response.data.total;

        } catch (error) {
            console.error('Error al cargar productos:', error);
            alert("Ocurrió un error al consultar los productos.");
        }
    },
    async cargarMaterialesProducto() {
        if (!this.producto.id || !this.producto.es_producto_compuesto) return;

        try {
            const response = await apiClient.get(`/api/materiales-producto/${this.producto.id}`);
            console.log('Materiales recibidos del endpoint:', response.data.materiales);
            this.materiales = response.data.materiales.map((material, index) => {
                const productoBase = this.productosDisponibles.find(p => p.id === material.producto_base_id);
                console.log(`Material ${index + 1}:`, material, 'Producto base:', productoBase);
                return {
                    id: material.id,
                    producto_base: material.producto_base_id,
                    nombreDigitado: productoBase ? productoBase.nombre : 'Producto no encontrado',
                    codigoDigitado: productoBase ? productoBase.codigo : 'N/A',
                    cantidad: material.cantidad,
                    peso_unitario: productoBase ? productoBase.peso_unidad_gr : material.peso_unitario,
                    peso_total: material.cantidad * (productoBase ? productoBase.peso_unidad_gr : material.peso_unitario)
                };
            });
            console.log('Materiales asignados a this.materiales:', this.materiales);
            this.actualizarPesoProductoCompuesto();
        } catch (error) {
            console.error('Error al cargar materiales del producto:', error);
            if (error.response && error.response.status === 404) {
                console.log(`No se encontraron materiales para el producto ${this.producto.id}`);
                this.materiales = [];
            } else {
                alert('No se pudieron cargar los materiales del producto compuesto.');
            }
        }
    },
    async cargarProductosDisponibles(materiales = []) {
        try {
            // Cargar solo los productos base necesarios para los materiales
            this.productosDisponibles = [];
            if (materiales.length > 0) {
                const productoBaseIds = materiales.map(m => m.producto_base_id);
                const response = await apiClient.get('/api/productos', {
                    params: {
                        producto_base_ids: productoBaseIds.join(',')
                    }
                });
                this.productosDisponibles = response.data.productos
                    .sort((a, b) => a.codigo.localeCompare(b.codigo));
                console.log('Productos base cargados:', this.productosDisponibles);
            }
        } catch (error) {
            console.error('Error al cargar productos disponibles:', error);
            if (error.response && error.response.status === 401) {
                alert('Sesión expirada. Por favor, inicia sesión nuevamente.');
                this.$router.push('/login');
            } else {
                alert('No se pudieron cargar los productos disponibles. Algunos materiales podrían no mostrarse correctamente.');
            }
        }
    },
    async cargarMasProductos(search = '') {
        try {
            const response = await apiClient.get('/api/productos', {
                params: {
                    search_codigo: search,
                    search_nombre: search,
                    limit: 500,
                    offset: this.productosDisponibles.length
                }
            });
            const nuevosProductos = response.data.productos;
            this.productosDisponibles = [
                ...this.productosDisponibles,
                ...nuevosProductos
            ].sort((a, b) => a.codigo.localeCompare(b.codigo));
            console.log('Productos adicionales cargados:', nuevosProductos);
        } catch (error) {
            console.error('Error al cargar más productos:', error);
            alert('No se pudieron cargar más productos.');
        }
    },
    actualizarPesoProductoCompuesto() {
        this.pesoTotalCalculado = this.materiales.reduce((total, material) => total + Number(material.peso_total), 0).toFixed(2);
        this.producto.peso_total_gr = this.pesoTotalCalculado;
        this.producto.peso_unidad_gr = this.pesoTotalCalculado;
    },
    async guardarMateriales() {
        try {
            // Validar que todos los materiales tengan valores válidos
            if (this.materiales.some(m => !m.producto_base || isNaN(m.cantidad) || m.cantidad <= 0)) {
                alert("Todos los materiales deben tener un producto base seleccionado y una cantidad válida mayor a 0.");
                return;
            }
            const payload = {
                producto_compuesto_id: this.producto.id,
                materiales: this.materiales.map(m => ({
                    producto_base_id: m.producto_base,
                    cantidad: Number(m.cantidad)  // Forzar a número explícitamente
                }))
            };

            await apiClient.post('/api/materiales-producto', payload);
            alert("Materiales guardados correctamente.");

            // Recalcular el peso después de guardar
            this.cargarMaterialesProducto();
            this.actualizarPesoProductoCompuesto();
        } catch (error) {
            console.error("Error al guardar materiales:", error);
            alert("Hubo un problema guardando los materiales.");
        }
    },

    // Nuevos métodos para actualización
  // Métodos para actualización
  cargarArchivoActualizarCsv(event) {
    this.archivoActualizarCsv = event.target.files[0];
    this.erroresActualizarCsv = '';
  },
  async procesarActualizacionCsv() {
    if (!this.archivoActualizarCsv) {
      alert("Por favor, selecciona un archivo CSV para actualizar.");
      return;
    }
    this.isLoadingActualizar = true;
    try {
      const formData = new FormData();
      formData.append('file', this.archivoActualizarCsv);
      const response = await apiClient.post('/api/productos/actualizar-csv', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 60000
      });
      const { message, productos_actualizados, productos_no_encontrados, errores } = response.data;
      let mensaje = `✅ ${message}\n\n`;
      if (productos_actualizados.length) {
        mensaje += `✔ Productos actualizados: ${productos_actualizados.join(', ')}\n`;
      }
      if (productos_no_encontrados.length) {
        mensaje += `⚠️ Productos no encontrados: ${productos_no_encontrados.join(', ')}\n`;
      }
      if (errores.length) {
        mensaje += `🛑 Errores detectados:\n- ${errores.join('\n- ')}\n\n`;
      }
      alert(mensaje);
      if (errores.length || productos_no_encontrados.length) {
        this.erroresActualizarCsv = `⚠️ Reporte de errores:\n\n`;
        if (productos_no_encontrados.length) {
          this.erroresActualizarCsv += `🔹 Productos no encontrados:\n- ${productos_no_encontrados.join('\n- ')}\n\n`;
        }
        if (errores.length) {
          this.erroresActualizarCsv += `🛑 Errores:\n- ${errores.join('\n- ')}\n`;
        }
      } else {
        this.erroresActualizarCsv = '';
      }
      this.archivoActualizarCsv = null;
      this.$refs.inputActualizarCsv.value = '';
      this.consultarProductos();
    } catch (error) {
      console.error('Error al actualizar productos desde CSV:', error);
      let mensajeError = "❌ Error al actualizar productos desde CSV.";
      if (error.code === 'ECONNABORTED') {
        mensajeError += " La solicitud tardó demasiado. Intenta con un archivo más pequeño.";
      } else if (error.response) {
        mensajeError += ` Detalles: ${error.response.data.error || 'Error desconocido'}`;
      }
      alert(mensajeError);
    } finally {
      this.isLoadingActualizar = false;
    }
  },
  limpiarActualizarCsv() {
    this.archivoActualizarCsv = null;
    this.$refs.inputActualizarCsv.value = '';
    this.erroresActualizarCsv = '';
  },
  descargarPlantillaActualizarCSV() {
    const csvContent =
      `# Instructivo: Llene los campos para actualizar productos existentes.\n` +
      `# 'codigo' es obligatorio y debe coincidir con un producto existente.\n` +
      `# Los demás campos son opcionales; déjelos en blanco para no modificarlos.\n` +
      `# Si 'es_producto_compuesto' es 'Sí', complete 'cantidad_productos', 'codigo1', 'cantidad1', etc.\n` +
      `# Los productos base deben existir.\n` +
      `# Nota: El código y el nombre deben ser únicos.\n` +
      `codigo,nombre,peso_total_gr,peso_unidad_gr,codigo_barras,es_producto_compuesto,stock_minimo,cantidad_productos,codigo1,cantidad1,codigo2,cantidad2\n` +
      `GRA12345678901234,Producto Base Actualizado,600,60,1234567890123,No,150,,,,\n` +
      `GRA98765432109876,Kit Compuesto Actualizado,,,9876543210987,Si,20,2,GRA12345678901234,3,GRA12199905000000,4\n`;
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.setAttribute('download', 'plantilla_actualizacion_productos.csv');
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  },
  mostrarInstructivoActualizar() {
    this.mostrarModalActualizar = true;
  },
  cerrarModalActualizar() {
    this.mostrarModalActualizar = false;
  },
  copiarErroresActualizar() {
    navigator.clipboard.writeText(this.erroresActualizarCsv).then(() => {
      alert('Errores copiados al portapapeles.');
    }).catch(err => {
      console.error('Error al copiar:', err);
    });
  },


    async cargarMasProductos() {
      try {
          this.offset += this.limit;
          const response = await apiClient.get(`/api/productos?offset=${this.offset}&limit=${this.limit}`);
          const nuevosProductos = response.data.productos.sort((a, b) => a.nombre.localeCompare(b.nombre));
          this.productos = [...this.productos, ...nuevosProductos];
      } catch (error) {
          console.error('Error al cargar más productos:', error);
      }
    },
    cargarCsv(event) {
    this.archivoCsv = event.target.files[0];
    },
    async procesarCsv() {
          if (!this.archivoCsv) {
              alert("Por favor, selecciona un archivo CSV.");
              return;
          }
          this.isLoadingCarga = true; // Mostrar spinner
          try {
              const formData = new FormData();
              formData.append('file', this.archivoCsv);
              const response = await apiClient.post('/api/productos/csv', formData, {
                  headers: { 'Content-Type': 'multipart/form-data' },
                  timeout: 60000 // 60 segundos
              });

              // Extraer datos de la respuesta
              const { message, productos_creados, productos_duplicados, errores } = response.data;

              // Construir el mensaje de éxito y errores
              let mensaje = `✅ ${message}\n\n`;
              if (productos_creados.length) {
                  mensaje += `✔ Productos creados: ${productos_creados.join(', ')}\n`;
              }
              if (productos_duplicados.length) {
                  mensaje += `⚠️ Productos duplicados (ya existen en la BD): ${productos_duplicados.join(', ')}\n`;
              }
              if (errores.length) {
                  mensaje += `🛑 Errores detectados:\n- ${errores.join('\n- ')}\n\n`;
              }
              alert(mensaje);

              // Guardar errores en una variable para mostrarlos en pantalla
              if (errores.length || productos_duplicados.length) {
                  this.erroresCsv = `⚠️ Reporte de errores:\n\n`;
                  if (productos_duplicados.length) {
                      this.erroresCsv += `🔹 Productos duplicados:\n- ${productos_duplicados.join('\n- ')}\n\n`;
                  }
                  if (errores.length) {
                      this.erroresCsv += `🛑 Errores:\n- ${errores.join('\n- ')}\n`;
                  }
              } else {
                  this.erroresCsv = ''; // Limpiar si no hay errores
              }

              // Volver a consultar los productos para reflejar los cambios
              this.consultarProductos();
          } catch (error) {
              console.error('Error al cargar archivo CSV:', error);
              let mensajeError = "❌ Error al cargar el archivo CSV.";
              if (error.code === 'ECONNABORTED') {
                  mensajeError += " La solicitud tardó demasiado. Intenta con un archivo más pequeño o contacta al soporte.";
              } else if (error.response) {
                  mensajeError += ` Detalles: ${error.response.data.error || 'Error desconocido'}`;
              }
              alert(mensajeError);
          } finally {
              this.isLoadingCarga = false; // Ocultar spinner
          }
      },

    // Sincroniza el input con el selector cuando el usuario escribe un código
    sincronizarSelector(index) {
        const material = this.materiales[index];
        const productoEncontrado = this.productosDisponibles.find(p => p.codigo === material.codigoDigitado);

        if (productoEncontrado) {
            material.producto_base = productoEncontrado.id;
            material.nombreDigitado = productoEncontrado.nombre; // ✅ También sincroniza el nombre
            this.actualizarPesoMaterial(index);
        }
    },

    // Sincroniza el selector con el input cuando el usuario selecciona en el dropdown
    sincronizarCodigo(index) {
        const material = this.materiales[index];
        const productoEncontrado = this.productosDisponibles.find(p => p.id === material.producto_base);

        if (productoEncontrado) {
            material.codigoDigitado = productoEncontrado.codigo;
            material.nombreDigitado = productoEncontrado.nombre; // ✅ También sincroniza el nombre
            this.actualizarPesoMaterial(index);
        }
    },

    sincronizarPorNombre(index) {
        const material = this.materiales[index];
        if (!material.nombreDigitado) return;
        const productoEncontrado = this.productosDisponibles.find(p => 
            p.nombre.toLowerCase().includes(material.nombreDigitado.toLowerCase())
        );
        if (productoEncontrado) {
            material.producto_base = productoEncontrado.id;
            material.codigoDigitado = productoEncontrado.codigo;
            this.actualizarPesoMaterial(index);
        } else {
            material.producto_base = null; // Resetear si no se encuentra
        }
    },

    editarProducto(producto) {
        this.modoEdicion = true;
        this.producto = { ...producto };
        this.cargarMaterialesProducto().then(() => {
            this.cargarProductosDisponibles(this.materiales);
        });
    },
    async actualizarProducto() {
        console.log('Datos enviados:', this.producto); // Depurar datos enviados
        try {
            await apiClient.put(`/api/productos/${this.producto.id}`, this.producto);
            alert('Producto actualizado correctamente');

            // Recargar la tabla de productos
            await this.consultarProductos();
            this.cancelarEdicion();

        } catch (error) {
            console.error('Error al actualizar producto:', error);
        }
    },
    cancelarEdicion() {
        this.modoEdicion = false;
        this.resetearFormulario();

        // Recargar la tabla después de cancelar
        this.consultarProductos();
    },
    resetearFormulario() {
    this.producto = {
        codigo: '',
        nombre: '',
        peso_total_gr: '',
        peso_unidad_gr: '',
        codigo_barras: '',
    };
    },

    //agregarMaterial() {
    //this.materiales.push({ producto_base: null, cantidad: 1, peso: 0 });
    //this.calcularPesoTotal();
    //},
    agregarMaterial() {
        this.materiales.push({ producto_base: null, cantidad: 1, peso_unitario: 0, peso_total: 0 });

    },
    async eliminarMaterial(index) {
        const material = this.materiales[index];
        if (material.id) {
            try {
                await apiClient.delete(`/api/materiales-producto/${material.id}`);
                alert("Material eliminado correctamente.");
            } catch (error) {
                console.error("Error al eliminar material:", error);
                alert("No se pudo eliminar el material.");
            }
        }
        this.materiales.splice(index, 1);
        this.actualizarPesoProductoCompuesto();
    },

  habilitarAgregarProductos() {
    this.agregarProductosVisible = true;
    this.nuevosMateriales = [{ producto_base: null, cantidad: 1, peso: 0 }];
  },
  agregarMaterialNuevo() {
    this.nuevosMateriales.push({ producto_base: null, cantidad: 1, peso: 0 });
  },
  async guardarNuevosMateriales() {
    try {
        for (const material of this.nuevosMateriales) {
            // Calcular el peso unitario para el material
            const productoBase = this.productosDisponibles.find(p => p.id === material.producto_base);
            if (productoBase) {
                material.peso = productoBase.peso_unidad_gr; // Asignar el peso unitario
            } //else {
                //material.peso = 0; // Manejo de errores si el producto no se encuentra
            //}

            // Enviar los datos al backend
            await apiClient.post('/api/materiales-producto', {
                producto_compuesto_id: this.productoSeleccionado,
                producto_base: material.producto_base,
                cantidad: material.cantidad,
                peso: material.peso,
            });
        }

        alert("Materiales agregados correctamente y peso actualizado.");
        this.agregarProductosVisible = false;
        this.nuevosMateriales = [];
        await this.consultarProductoCompuesto(); // Refrescar los datos tras agregar materiales
    } catch (error) {
        console.error("Error al guardar nuevos materiales:", error);
        alert("Ocurrió un error al agregar los materiales. Verifique la conexión y los datos.");
    }
  },
  async eliminarProducto(productoId) {
    try {
        const confirmacion = confirm("¿Estás seguro de que deseas eliminar este producto?");
        if (!confirmacion) return;

        const response = await apiClient.delete(`/api/productos/${productoId}`);
        alert(response.data.message);

        // Actualizar la lista de productos después de eliminar
        this.productos = this.productos.filter(prod => prod.id !== productoId);
        this.totalProductos -= 1;
    } catch (error) {
        console.error("Error al eliminar producto:", error);
        alert("No se pudo eliminar el producto. Revisa la consola para más detalles.");
    }
  },


  async eliminarProductoCompuesto() {
    try {
        await apiClient.delete(`/api/productos-compuestos/${this.productoSeleccionado}`);
        alert("Producto compuesto eliminado correctamente.");
        this.materialesProductoCompuesto = [];
        this.pesoTotalCalculado = 0;
    } catch (error) {
        console.error("Error al eliminar producto compuesto:", error);
        alert("Ocurrió un error al eliminar el producto compuesto.");
    }
  },
  calcularPesoTotal() {
    this.pesoTotalCalculado = this.materiales.reduce((total, material) => {
      const producto = this.productosDisponibles.find((p) => p.id === material.producto_base);
      return total + (producto ? producto.peso_unidad_gr * material.cantidad : 0);
    }, 0);
  },
  actualizarPesoMaterial(index) {
        const material = this.materiales[index];
        const producto = this.productosDisponibles.find(p => p.id === material.producto_base);

        if (producto) {
            material.peso_unitario = producto.peso_unidad_gr;
            material.peso_total = material.cantidad * material.peso_unitario;
        } else {
            material.peso_unitario = 0;
            material.peso_total = 0;
        }

        this.actualizarPesoProductoCompuesto();
    },
  async crearProductoCompuesto() {
    try {
      const payload = {
        ...this.nuevoProducto,
        peso_total: this.pesoTotalCalculado,
        materiales: this.materiales.map((material) => ({
          producto_base: material.producto_base,
          cantidad: material.cantidad,
          peso: material.peso,
        })),
      };
      await apiClient.post("/api/productos-compuestos", payload);
      alert("Producto compuesto creado correctamente");
      this.nuevoProducto = { codigo: "", nombre: "", codigo_barras: "" };
      this.materiales = [];
      this.pesoTotalCalculado = 0;
      this.cargarProductos();
    } catch (error) {
      console.error("Error al crear producto compuesto:", error);
      alert("Ocurrió un error al crear el producto compuesto.");
    }
  },
  async consultarProductoCompuesto(tipo) {
    try {
        let params = {};
        if (tipo === 'id') {
            params.id = this.productoSeleccionado;
        } else if (tipo === 'codigo') {
            params.codigo = this.codigoProducto;
        }

        const response = await apiClient.get('/api/productos-compuestos/detalle', { params });
        const data = response.data;

        this.materialesProductoCompuesto = data.materiales.map((material) => ({
            id: material.id,
            producto_base_codigo: material.producto_base_codigo,
            producto_base_nombre: material.producto_base_nombre,
            cantidad: material.cantidad,
            peso_unitario: material.peso_unitario,
            peso_total: material.peso_total,
        }));

        this.pesoTotalCalculado = data.producto.peso_total_gr;
    } catch (error) {
        console.error("Error al consultar producto compuesto:", error);
        alert("No se pudo realizar la consulta del producto compuesto. Inténtelo nuevamente.");
    }
  },
  actualizarPesoTotalMaterial(index) {
        const material = this.materialesProductoCompuesto[index];
        const productoBase = this.productosDisponibles.find(
            (p) => p.codigo === material.producto_base_codigo
        );

        if (productoBase) {
            material.peso_unitario = productoBase.peso_unidad_gr;
        }

        material.peso_total = material.peso_unitario * material.cantidad;

        this.pesoTotalCalculado = this.materialesProductoCompuesto.reduce(
            (total, mat) => total + mat.peso_total,
            0
        );
  },
  async guardarCambiosMaterial(material) {
        try {
            if (!material.id) {
            throw new Error("El ID del material no está definido.");
            }

            // Actualizar el peso unitario basado en la cantidad y el producto base
            const productoBase = this.productosDisponibles.find(
            (p) => p.codigo === material.producto_base_codigo
            );
            if (productoBase) {
            material.peso_unitario = productoBase.peso_unidad_gr; // Peso unitario del producto base
            }

            console.log("Intentando guardar cambios para el material:", material);

            const response = await apiClient.put(`/api/materiales-producto/${material.id}`, {
            cantidad: material.cantidad,
            peso_unitario: material.peso_unitario, // Enviar el peso unitario actualizado
            });

            console.log("Cambios guardados correctamente:", response.data);
            alert("Cambios guardados correctamente.");

            // Recalcular el peso total del producto compuesto después de guardar
            this.calcularPesoTotal();
        } catch (error) {
            console.error("Error al guardar cambios en material:", error);
            alert("Ocurrió un error al guardar los cambios.");
        }
  },
  async eliminarMaterialDelProductoCompuesto(materialId) {
        try {
            await apiClient.delete(`/api/materiales-producto/${materialId}`);
            alert("Material eliminado correctamente.");

            // Recargar los materiales del producto compuesto
            this.consultarProductoCompuesto();
        } catch (error) {
            console.error("Error al eliminar material:", error);
            alert("Ocurrió un error al eliminar el material.");
        }
  },
  async exportarAExcel() {
    try {
        // Obtener todos los productos sin paginación
        const response = await apiClient.get('/api/productos', {
        params: {
            offset: 0,
            limit: 10000, // Límite alto para asegurar que traiga todos
            search_codigo: this.filtroCodigo || '',
            search_nombre: this.filtroNombre || ''
        }
        });

        const productosTodos = response.data.productos;

        // Preparar los datos para el Excel
        const worksheetData = [
        ["Productos Cargados"],
        ["Código", "Nombre", "Peso Total (g)", "Peso Unidad (g)", "Código de Barras", "Prod. Compuesto", "Stock Mínimo"],
        ...productosTodos.map(prod => [
            prod.codigo,
            prod.nombre,
            prod.peso_total_gr !== null ? prod.peso_total_gr : '',
            prod.peso_unidad_gr !== null ? prod.peso_unidad_gr : '',
            prod.codigo_barras || '',
            prod.es_producto_compuesto ? 'Sí' : 'No',
            prod.stock_minimo !== null ? prod.stock_minimo : ''
        ])
        ];

        // Crear la hoja y el libro de Excel
        const worksheet = XLSX.utils.aoa_to_sheet(worksheetData);
        const workbook = XLSX.utils.book_new();
        XLSX.utils.book_append_sheet(workbook, worksheet, "Productos");

        // Descargar el archivo
        XLSX.writeFile(workbook, `Productos_Cargados_${new Date().toISOString().slice(0,10)}.xlsx`);
    } catch (error) {
        console.error('Error al exportar a Excel:', error);
        alert("Ocurrió un error al exportar los productos a Excel.");
    }
},
  copiarErrores() {
        navigator.clipboard.writeText(this.erroresCsv).then(() => {
            alert("Errores copiados al portapapeles.");
        }).catch(err => {
            console.error("Error al copiar:", err);
        });
},
  limpiarPagina() {
        // Restablecer el formulario
        this.producto = {
            id: null,
            codigo: '',
            nombre: '',
            es_producto_compuesto: false,
            peso_total_gr: '',
            peso_unidad_gr: '',
            codigo_barras: ''
        };

        // Limpiar la tabla de productos y filtros
        this.productos = [];
        this.filtroCodigo = '';
        this.totalProductos = 0;

        //alert("Página limpiada correctamente.");
  },

  limpiarCampos() {
        this.filtroCodigo = '';  // Limpiar campo de búsqueda por código
        this.filtroNombre = '';  // Limpiar campo de búsqueda por nombre
        this.productos = [];     // Vaciar la tabla de productos
        this.totalProductos = 0; // Resetear total de productos
  },

  limpiarSesionCsv() {
    this.archivoCsv = null;  // Limpiar el archivo seleccionado
    this.erroresCsv = '';    // Limpiar los errores mostrados
    this.$refs.inputCsv.value = ''; // Resetear el input de archivos (si agregamos ref en el input)
    //alert("Sesión de carga de productos restablecida.");
  },

  limpiarSesion() {
    // Restablecer el formulario del producto
    this.producto = {
        id: null,
        codigo: '',
        nombre: '',
        es_producto_compuesto: false,
        peso_total_gr: '',
        peso_unidad_gr: '',
        codigo_barras: ''
    };

    // Limpiar los materiales del producto
    this.materiales = [];

    // Desactivar el modo edición
    this.modoEdicion = false;

    // Ocultar la sección de materiales
    this.producto.es_producto_compuesto = false;

    //alert("Sesión de creación/edición limpiada correctamente.");
  },

  descargarPlantillaCSV() {
    // Contenido del CSV con encabezados y ejemplos
    const csvContent = 
        `# Instructivo: Llene los campos según corresponda.\n` +
        `# Si "es_producto_compuesto" es "Sí", debe completar las columnas de "cantidad_productos", "codigo1", "cantidad1", "codigo2", etc.\n` +
        `# Si el porducto es Base, se coloca cero 0. Si el producto es compuesto, indicar cuántos productos base lo conforman.\n` +
        `# "stock_minimo" es opcional; déjelo en blanco si no aplica.\n` +
        `# Los productos base deben estar previamente creados.\n` +
        `codigo,nombre,peso_total_gr,peso_unidad_gr,codigo_barras,es_producto_compuesto,stock_minimo,cantidad_productos,codigo1,cantidad1,codigo2,cantidad2\n` +
        `GRA12345678901234,Ejemplo Producto Base,500,50,1234567890123,No,100,0,,,,\n` +
        `GRA98765432109876,Ejemplo Producto Compuesto,,,9876543210987,Si,10,2,GRA12345678901234,2,GRA12199905000000,3\n`;

    // Crear un Blob con el contenido CSV y definir su tipo
    const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });

    // Crear un enlace temporal para la descarga
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.setAttribute("download", "Plantilla_Carga_Productos.csv");
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  },

  mostrarInstructivo() {
    this.mostrarModal = true;
  },

  cerrarModal() {
    this.mostrarModal = false;
  },


  volverAlMenu() {
        const tipoUsuario = localStorage.getItem("tipo_usuario"); // Obtener el tipo de usuario del almacenamiento local

        if (tipoUsuario === "admin") {
        this.$router.push('/menu'); // Redirigir al menú del administrador
        } else if (tipoUsuario === "gerente") {
        this.$router.push('/menu-gerente'); // Redirigir al menú del gerente
        } else {
        alert("Rol no reconocido. Contacta al administrador."); // Manejo de error en caso de un rol desconocido
        }
  },
},
mounted() {
        
    //this.cargarProductosDisponibles();
    this.cargarProductosDisponibles().then(() => {
        console.log("Productos disponibles al montar:", this.productosDisponibles);
    }); 
},

watch: {
        'producto.id': function (newVal) {
            if (newVal) {
                this.cargarMaterialesProducto();
            }
        }
}
};
</script>

<style scoped>
/* Contenedor principal */
.produccion-admin {
margin: 20px auto;
max-width: 1200px;
font-family: Arial, sans-serif;
padding: 10px;
}

/* Títulos */
h1 {
text-align: center;
color: #333;
margin-bottom: 20px;
}

h2, h3 {
color: #0056b3;
margin-bottom: 15px;
}

/* Botones */
button {
padding: 0.6rem 1.2rem;
border: none;
background-color: #007bff;
color: #fff;
cursor: pointer;
border-radius: 4px;
font-size: 14px;
margin-right: 10px;
}

button:hover {
background-color: #0056b3;
box-shadow: 0px 4px 6px rgba(0, 0, 0, 0.2);
}

button.btn-warning {
background-color: #ffc107; /* Amarillo para advertencias */
color: #333; /* Texto oscuro */
}

button.btn-warning:hover {
background-color: #e0a800; /* Amarillo más oscuro */
}

/* Formularios */
form label {
font-weight: bold;
display: block;
margin-bottom: 5px;
color: #555;
}

form input, form select {
width: 100%;
padding: 10px;
margin-bottom: 15px;
border: 1px solid #ccc;
border-radius: 4px;
font-size: 14px;
}

/* Tablas */
table {
width: 100%;
border-collapse: collapse;
margin-top: 20px;
font-size: 14px;
}

th, td {
border: 1px solid #ddd;
padding: 10px;
text-align: left;
}

th {
background-color: #f8f9fa;
color: #333;
font-weight: bold;
}

tbody tr:nth-child(odd) {
background-color: #f9f9f9;
}

tbody tr:hover {
background-color: #f1f1f1;
}

/* Secciones */
section {
margin-bottom: 30px;
padding: 15px;
border: 1px solid #e9ecef;
border-radius: 6px;
background-color: #f8f9fa;
}

/* Historial de entregas */
p {
margin: 5px 0;
color: #555;
font-size: 14px;
}

/* --- Responsividad --- */
@media (max-width: 768px) {
/* Reducir márgenes en pantallas pequeñas */
.produccion-admin {
margin: 10px auto;
padding: 10px;
}

.filtros {
    flex-direction: column; /* Hace que los filtros se apilen en pantallas pequeñas */
}

.filtro-item {
    width: 100%;
}

/* Formularios en columna */
form input, form select, button {
width: 100%;
margin-bottom: 10px;
font-size: 16px;
}

/* Tablas desplazables horizontalmente */
table {
display: block;
overflow-x: auto;
white-space: nowrap;
}

th, td {
font-size: 12px;
padding: 8px;
}

/* Reducir tamaño de títulos */
h1 {
font-size: 20px;
}

h2, h3 {
font-size: 18px;
}
}

/* Sección mejorada para la consulta de productos */
.consulta-productos {
padding: 15px;
border: 1px solid #e9ecef;
border-radius: 6px;
background-color: #f8f9fa;
margin-bottom: 30px;
}

/* Contenedor de filtros */
.filtros {
display: flex;
flex-wrap: wrap;
gap: 15px;
align-items: center;
margin-bottom: 15px;
}

/* Cada filtro se comporta bien en cualquier tamaño de pantalla */
.filtro-item {
flex: 1; /* Que cada input tenga el mismo tamaño */
min-width: 200px; /* Evita que sean muy pequeños */
}

.filtro-boton {
display: flex;
align-items: flex-end; /* Alinear el botón en la parte inferior */
}

/* Contenedor responsivo de la tabla */
.tabla-container {
overflow-x: auto; /* Permite desplazamiento horizontal en móviles */
}

/* Botón Limpiar Campos */
.btn-limpiar {
background-color: #ffc107;
color: #333; /* Texto oscuro */
padding: 0.6rem 1.2rem;
border: none;
cursor: pointer;
border-radius: 4px;
font-size: 14px;
margin-left: 10px;

}

.btn-limpiar:hover {
background-color: #e0a800;
}

/* Botones adicionales */
.btn-secundario {
background-color: #28a745;
color: white;
padding: 10px;
border: none;
cursor: pointer;
margin-left: 10px;
}

.btn-secundario:hover {
background-color: #218838;
}

.btn-info {
background-color: #17a2b8;
color: white;
padding: 10px;
border: none;
cursor: pointer;
margin-left: 10px;
}

.btn-info:hover {
background-color: #138496;
}

/* Modal de Instructivo */
.modal-instructivo {
position: fixed;
top: 0;
left: 0;
width: 100%;
height: 100%;
background-color: rgba(0, 0, 0, 0.5);
display: flex;
justify-content: center;
align-items: center;
}

.modal-contenido {
background: white;
padding: 20px;
border-radius: 8px;
text-align: left;
max-width: 500px;
}

.btn-cerrar {
background-color: #dc3545;
color: white;
padding: 10px;
border: none;
cursor: pointer;
margin-top: 10px;
}

.btn-cerrar:hover {
background-color: #c82333;
}

/* Sección de carga CSV */
.carga-csv {
padding: 15px;
border: 1px solid #e9ecef;
border-radius: 6px;
background-color: #f8f9fa;
margin-bottom: 30px;

}

/* Título alineado a la izquierda */
.carga-csv h2 {
text-align: left;
}

/* Contenedor de los botones */
.carga-input {
display: flex;
flex-wrap: wrap;
justify-content: flex-start; /* Alinear a la izquierda */
gap: 10px;
margin-bottom: 10px;
}

/* Links para descarga e instructivo */
.carga-links {
display: flex;
justify-content: flex-start; /* Alinear enlaces a la izquierda */
gap: 20px;
margin-bottom: 10px;
}

/* Estilos de los enlaces de descarga */
.link-descarga, .link-instructivo {
color: #007bff;
text-decoration: none;
font-weight: bold;
cursor: pointer;
}

.link-descarga:hover, .link-instructivo:hover {
text-decoration: underline;
}

/* Contenedor de errores */
.error-container {
margin-top: 15px;
background-color: #fff3cd;
padding: 10px;
border-radius: 6px;
text-align: center;
}

.error-container textarea {
width: 100%;
height: 100px;
font-size: 14px;
border: 1px solid #ccc;
padding: 5px;
resize: none;
}

/* Spinner */
.spinner-container {
display: flex;
flex-direction: column;
align-items: center;
margin-bottom: 15px;
}

.spinner {
border: 4px solid #f3f3f3; /* Color claro */
border-top: 4px solid #007bff; /* Color principal */
border-radius: 50%;
width: 30px;
height: 30px;
animation: spin 1s linear infinite;
margin-bottom: 10px;
}

.spinner-container p {
color: #555;
font-size: 14px;
}

.card {
background: #fff;
padding: 20px;
margin-bottom: 20px;
border-radius: 8px;
box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.input-file {
margin: 10px 0;
}

.button-group {
display: flex;
gap: 10px;
align-items: center;
flex-wrap: wrap;
}

.button-group button,
.button-group a {
padding: 10px 20px;
border: none;
border-radius: 4px;
cursor: pointer;
text-decoration: none;
}

.button-group button {
background: #28a745;
color: white;
}

.button-group button:disabled {
background: #ccc;
cursor: not-allowed;
}

.button-group a {
background: #007bff;
color: white;
display: inline-block;
}

.spinner-container {
display: flex;
flex-direction: column;
align-items: center;
margin-top: 20px;
}

.spinner {
border: 4px solid #f3f3f3;
border-top: 4px solid #3498db;
border-radius: 50%;
width: 40px;
height: 40px;
animation: spin 1s linear infinite;
}

@keyframes spin {
0% { transform: rotate(0deg); }
100% { transform: rotate(360deg); }
}

.errores-csv {
margin-top: 20px;
background: #f8d7da;
padding: 10px;
border-radius: 4px;
}

.errores-csv pre {
white-space: pre-wrap;
margin: 0;
}

.errores-csv button {
background: #dc3545;
color: white;
margin-top: 10px;
}

@keyframes spin {
0% { transform: rotate(0deg); }
100% { transform: rotate(360deg); }
}

</style>





