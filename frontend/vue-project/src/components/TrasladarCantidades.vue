<template>
  <div class="trasladar-cantidades">
    <h1>Trasladar Cantidades entre Bodegas</h1>

    <!-- Botón para volver al menú principal -->
    <section class="menu-button">
      <button @click="volverAlMenu" class="btn btn-secondary">Volver al Menú Principal</button>
      <button @click="limpiarPagina" class="btn btn-warning">Limpiar Página</button>
    </section>

    <!-- Consulta de Inventario -->
    <section class="consulta-inventario">
      <h2>Consulta de Inventario</h2>
      <div class="form-group">
        <label for="nombreConsulta">Buscar por nombre:</label>
        <input 
          v-model="nombreConsulta"
          id="nombreConsulta"
          placeholder="Ingrese nombre del producto"
          class="form-control"
          @input="sincronizarPorNombre"
        />
      </div>
      <div class="form-group">
        <label for="productoConsulta">Seleccione un producto:</label>
        <select v-model="productoConsulta" id="productoConsulta" class="form-control" @change="sincronizarSelectorConCodigo">
          <option value="" disabled>Seleccione un producto</option>
          <option v-for="producto in productos" :key="producto.id" :value="producto.codigo">
            {{ producto.codigo }} - {{ producto.nombre }}
          </option>
        </select>
      </div>
      <div class="form-group">
        <label for="codigoConsulta">O ingrese el código del producto:</label>
        <input 
          v-model="codigoConsulta"
          id="codigoConsulta"
          placeholder="Ingrese código del producto"
          class="form-control"
          @input="sincronizarCodigoConSelector"
        />
        <button @click="consultarInventario" class="btn btn-primary">Consultar Inventario</button>
      </div>

      <div v-if="inventario.length" class="inventario-producto">
        <h3>Inventario del Producto</h3>
        <table>
          <thead>
            <tr>
              <th>Código</th>
              <th>Nombre</th>
              <th v-for="bodega in bodegas" :key="bodega.id">{{ bodega.nombre }}</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>{{ inventarioProducto.codigo }}</td>
              <td>{{ inventarioProducto.nombre }}</td>
              <td v-for="bodega in bodegas" :key="bodega.id">
                {{ obtenerCantidadEnBodega(bodega.nombre) }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- Selección de Productos para Traslado -->
    <section class="productos-traslado">
      <h2>Agregar Productos al Traslado</h2>
      <div class="form-group">
        <label for="nombreTraslado">Buscar por nombre:</label>
        <input 
          v-model="nombreTraslado"
          id="nombreTraslado"
          placeholder="Ingrese nombre del producto"
          class="form-control"
          @input="sincronizarPorNombreTraslado"
        />
      </div>
      <div class="form-group">
        <label for="codigo">Código del Producto:</label>
        <select v-model="nuevoTraslado.codigo" id="codigo" class="form-control" @change="sincronizarSelectorConCodigoTraslado">
          <option value="" disabled>Seleccione un producto</option>
          <option v-for="producto in productos" :key="producto.id" :value="producto.codigo">
            {{ producto.codigo }} - {{ producto.nombre }}
          </option>
        </select>
      </div>
      <div class="form-group">
        <label for="codigoIngresado">O ingrese el código del producto:</label>
        <input 
          v-model="codigoTraslado"
          id="codigoIngresado"
          placeholder="Ingrese código del producto"
          class="form-control"
          @input="sincronizarCodigoConSelectorTraslado"
        />
      </div>

      <div class="form-group">
        <label for="bodega_origen">Bodega Origen:</label>
        <select v-model="nuevoTraslado.bodega_origen" id="bodega_origen" class="form-control">
          <option value="" disabled>Seleccione una bodega</option>
          <option v-for="bodega in bodegas" :key="bodega.id" :value="bodega.nombre">
            {{ bodega.nombre }}
          </option>
        </select>
      </div>
      <div class="form-group">
        <label for="bodega_destino">Bodega Destino:</label>
        <select v-model="nuevoTraslado.bodega_destino" id="bodega_destino" class="form-control">
          <option value="" disabled>Seleccione una bodega</option>
          <option v-for="bodega in bodegas" :key="bodega.id" :value="bodega.nombre">
            {{ bodega.nombre }}
          </option>
        </select>
      </div>
      <div class="form-group">
        <label for="cantidad">Cantidad:</label>
        <input v-model.number="nuevoTraslado.cantidad" id="cantidad" type="number" class="form-control" />
      </div>
      <button @click="agregarProductoATraslado" class="btn btn-success">Agregar Producto al Traslado</button>
    </section>

    <!-- Tabla Temporal de Productos a Trasladar -->
    <section v-if="productosATrasladar.length" class="productos-en-traslado">
      <h2>Productos en el Traslado</h2>
      <table>
        <thead>
          <tr>
            <th>Código</th>
            <th>Nombre</th>
            <th>Bodega Origen</th>
            <th>Bodega Destino</th>
            <th>Cantidad</th>
            <th>Costo Unitario</th>
            <th>Costo Total</th>
            <th>Acciones</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(producto, index) in productosATrasladar" :key="index">
            <td>{{ producto.codigo }}</td>
            <td>{{ producto.nombre }}</td>
            <td>{{ producto.bodega_origen }}</td>
            <td>{{ producto.bodega_destino }}</td>
            <td>{{ producto.cantidad }}</td>
            <td>{{ producto.costo_unitario ? `$${producto.costo_unitario.toFixed(2)}` : 'N/A' }}</td>
            <td>{{ producto.costo_total ? `$${producto.costo_total.toFixed(2)}` : 'N/A' }}</td>
            <td>
              <button @click="eliminarProductoDelTraslado(index)" class="btn btn-danger">Eliminar</button>
            </td>
          </tr>
        </tbody>
      </table>
      <button @click="confirmarTraslado" class="btn btn-primary">Trasladar Productos</button>
    </section>

    <!-- Consulta de Traslados -->
    <section class="consulta-traslados">
      <h2>Consulta de Traslados</h2>
      <div class="form-group">
        <label for="nombreConsultaTraslados">Buscar por nombre:</label>
        <input 
          v-model="nombreConsultaTraslados"
          id="nombreConsultaTraslados"
          placeholder="Ingrese nombre del producto"
          class="form-control"
          @input="sincronizarPorNombreTraslados"
        />
      </div>
      <div class="form-group">
        <label for="productoConsultaTraslados">Producto:</label>
        <select v-model="filtroProducto" id="productoConsultaTraslados" class="form-control" @change="sincronizarSelectorConCodigoTraslados">
          <option value="" disabled>Seleccione un producto</option>
          <option v-for="producto in productos" :key="producto.id" :value="producto.codigo">
            {{ producto.codigo }} - {{ producto.nombre }}
          </option>
        </select>
      </div>
      <div class="form-group">
        <label for="codigoConsultaTraslados">O ingrese el código del producto:</label>
        <input 
          v-model="codigoConsultaTraslados"
          id="codigoConsultaTraslados"
          placeholder="Ingrese código del producto"
          class="form-control"
          @input="sincronizarCodigoConSelectorTraslados"
        />
      </div>

      <div class="form-group">
        <label for="consecutivo">Consecutivo:</label>
        <input v-model="filtroConsecutivo" id="consecutivo" placeholder="Ingrese consecutivo" class="form-control" />
      </div>
      <div class="form-group">
        <label for="fechaInicio">Fecha inicio:</label>
        <input type="date" id="fechaInicio" v-model="fechaInicio" class="form-control" />
        <label for="fechaFin">Fecha fin:</label>
        <input type="date" id="fechaFin" v-model="fechaFin" class="form-control" />
      </div>
      <!-- Nuevos filtros por Bodega de Origen y Destino -->
      <div class="form-group">
        <label for="filtroBodegaOrigen">Bodega de Origen:</label>
        <select v-model="filtroBodegaOrigen" id="filtroBodegaOrigen" class="form-control">
          <option value="" disabled>Seleccione una bodega</option>
          <option v-for="bodega in bodegas" :key="bodega.id" :value="bodega.nombre">
            {{ bodega.nombre }}
          </option>
        </select>
      </div>
      <div class="form-group">
        <label for="filtroBodegaDestino">Bodega de Destino:</label>
        <select v-model="filtroBodegaDestino" id="filtroBodegaDestino" class="form-control">
          <option value="" disabled>Seleccione una bodega</option>
          <option v-for="bodega in bodegas" :key="bodega.id" :value="bodega.nombre">
            {{ bodega.nombre }}
          </option>
        </select>
      </div>
      <button @click="consultarTraslados" class="btn btn-primary">Consultar Traslados</button>

      <div v-if="traslados.length" class="resultados-traslados">
        <h3>Resultados de la Consulta</h3>
        <div>
          <button @click="imprimirTrasladosPDF" class="btn btn-success">Imprimir Listado <i class="fas fa-file-pdf pdf-icon"></i></button>
          <button @click="exportarTrasladosExcel" class="btn btn-primary">Exportar Listado <i class="fas fa-file-excel excel-icon"></i></button>
        </div>
        <table>
          <thead>
            <tr>
              <th>Consecutivo</th>
              <th>Fecha</th>
              <th>Acción</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="traslado in traslados" :key="traslado.consecutivo">
              <td>{{ traslado.consecutivo }}</td>
              <td>{{ traslado.fecha }}</td>
              <td>
                <button @click="verDetalleTraslado(traslado.consecutivo)" class="btn btn-info">Detalle</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Detalle del Traslado -->
      <section v-if="detalleTraslado.length" class="detalle-traslado">
        <h3>Detalle del Traslado {{ trasladoSeleccionado }}</h3>
        <div>
          <button @click="imprimirDetalleTrasladoPDF" class="btn btn-success">Imprimir <i class="fas fa-file-pdf pdf-icon"></i></button>
          <button @click="exportarDetalleTrasladoExcel" class="btn btn-primary">Exportar <i class="fas fa-file-excel excel-icon"></i></button>
        </div>
        <table>
          <thead>
            <tr>
              <th>Consecutivo</th>
              <th>Fecha</th>
              <th>Producto</th>
              <th>Cantidad</th>
              <th>Bodega Origen</th>
              <th>Bodega Destino</th>
              <th>Costo Unitario</th>
              <th>Costo Total</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in detalleTraslado" :key="item.id">
              <td>{{ item.consecutivo }}</td>
              <td>{{ item.fecha }}</td>
              <td>{{ item.producto }}</td>
              <td>{{ item.cantidad }}</td>
              <td>{{ item.bodega_origen }}</td>
              <td>{{ item.bodega_destino }}</td>
              <td>{{ item.costo_unitario ? `$${item.costo_unitario.toFixed(2)}` : 'N/A' }}</td>
              <td>{{ item.costo_total ? `$${item.costo_total.toFixed(2)}` : 'N/A' }}</td>
            </tr>
          </tbody>
        </table>
      </section>
    </section>
  </div>
</template>


<script>
import apiClient from "../services/axios";
import * as XLSX from "xlsx";

export default {
  name: "TrasladarCantidades",
  data() {
    return {
      productoConsulta: "",
      nombreConsulta: "",
      codigoConsulta: "",
      nuevoTraslado: {
        codigo: "",
        bodega_origen: "",
        bodega_destino: "",
        cantidad: 0,
      },
      nombreTraslado: "",
      codigoTraslado: "",
      productos: [],
      bodegas: [],
      productosATrasladar: [],
      inventario: [],
      inventarioProducto: {
        codigo: "",
        nombre: "",
      },
      filtroConsecutivo: "",
      filtroProducto: "",
      nombreConsultaTraslados: "",  // ✅ Nuevo campo para búsqueda por nombre en "Consulta de Traslados"
      codigoConsultaTraslados: "",
      fechaInicio: "",
      fechaFin: "",
      filtroBodegaOrigen: "", // Nuevo filtro para Bodega de Origen
      filtroBodegaDestino: "", // Nuevo filtro para Bodega de Destino
      traslados: [],
      detalleTraslado: [], // Nueva propiedad para el detalle
      trasladoSeleccionado: "", // Consecutivo del traslado seleccionado
    };
  },
  methods: {
    limpiarPagina() {
      // 🔹 Limpiar la sección "Consulta de Inventario"
      this.productoConsulta = "";
      this.nombreConsulta = "";
      this.codigoConsulta = "";
      this.inventario = [];
      this.inventarioProducto = { codigo: "", nombre: "" };

      // 🔹 Limpiar la sección "Agregar Productos al Traslado"
      this.nuevoTraslado = {
        codigo: "",
        bodega_origen: "",
        bodega_destino: "",
        cantidad: 0,
      };
      this.nombreTraslado = "";
      this.codigoTraslado = "";

         // 🔹 Limpiar la sección "Productos en el Traslado"
      this.productosATrasladar = [];


      // 🔹 Limpiar la sección "Consulta de Traslados"
      this.nombreConsultaTraslados = "";
      this.codigoConsultaTraslados = "";
      this.filtroConsecutivo = "";
      this.filtroProducto = "";
      this.fechaInicio = "";
      this.fechaFin = "";
      this.filtroBodegaOrigen = ""; // Limpiar filtro
      this.filtroBodegaDestino = ""; // Limpiar filtro
      this.traslados = [];
      this.detalleTraslado = []; // Limpiar detalle
      this.trasladoSeleccionado = "";
    },
    async cargarProductos() {
      try {
        const response = await apiClient.get("/api/productos/completos");
        // Ordenar los productos por código ascendente
        this.productos = response.data.sort((a, b) => a.codigo.localeCompare(b.codigo));

      } catch (error) {
        console.error("Error al cargar productos:", error);
        alert("No se pudieron cargar los productos.");
      }
    },
    async cargarBodegas() {
      try {
        const response = await apiClient.get("/api/bodegas");
        this.bodegas = response.data;
      } catch (error) {
        console.error("Error al cargar bodegas:", error);
      }
    },
    async consultarInventario() {
      if (!this.productoConsulta) {
        alert("Seleccione un producto para consultar su inventario");
        return;
      }
      try {
        const response = await apiClient.get(`/api/inventario/${this.productoConsulta}`);

        // Verificar si el inventario está vacío
        if (response.data.message) {
          alert(response.data.message); // Mostrar el mensaje del backend
          this.inventarioProducto = { codigo: "", nombre: "" };
          this.inventario = [];
          return;
        }

        // Procesar la respuesta si hay inventario
        this.inventarioProducto = response.data.producto;
        this.inventario = response.data.inventario;
      } catch (error) {
        console.error("Error al consultar inventario:", error);
        alert("Ocurrió un error inesperado al consultar el inventario.");
      }
    },
    obtenerCantidadEnBodega(nombreBodega) {
      const bodega = this.inventario.find((inv) => inv.bodega === nombreBodega);
      return bodega ? bodega.cantidad : 0;
    },
    async agregarProductoATraslado() {
      if (
        !this.nuevoTraslado.codigo ||
        !this.nuevoTraslado.bodega_origen ||
        !this.nuevoTraslado.bodega_destino ||
        !this.nuevoTraslado.cantidad
      ) {
        alert("Complete todos los campos antes de agregar el producto.");
        return;
      }
      const producto = this.productos.find((p) => p.codigo === this.nuevoTraslado.codigo);
      
      // Consultar costo unitario desde Kardex
      try {
        const hoy = new Date().toISOString().split('T')[0]; // Fecha actual: 2025-04-03
        const response = await apiClient.get(`/api/kardex`, {
          params: {
            codigo: this.nuevoTraslado.codigo,
            fecha_inicio: '2025-01-01', // Fecha inicial amplia para capturar movimientos previos
            fecha_fin: hoy,
          }
        });

        // Filtrar movimientos relevantes para la bodega origen
        const ultimoMovimiento = response.data.kardex
          .filter(m => m.bodega === this.nuevoTraslado.bodega_origen && m.tipo !== 'SALIDA')
          .sort((a, b) => new Date(b.fecha) - new Date(a.fecha))[0];
        
        const costo_unitario = ultimoMovimiento ? ultimoMovimiento.saldo_costo_unitario : 0.0;
        const costo_total = costo_unitario * this.nuevoTraslado.cantidad;

        this.productosATrasladar.push({
          ...this.nuevoTraslado,
          nombre: producto.nombre,
          costo_unitario,
          costo_total
        });
        this.nuevoTraslado = { codigo: "", bodega_origen: "", bodega_destino: "", cantidad: 0 };
      } catch (error) {
        console.error("Error al obtener costo unitario:", error);
        if (error.response && error.response.data && error.response.data.message) {
          alert(`Error en la solicitud: ${error.response.data.message}`);
        } else {
          alert("No se pudo obtener el costo unitario del producto.");
        }
      }
    },
    eliminarProductoDelTraslado(index) {
      this.productosATrasladar.splice(index, 1);
    },
    async confirmarTraslado() {
      if (!this.productosATrasladar.length) {
        alert("Debe agregar al menos un producto al traslado.");
        return;
      }
      try {
        const response = await apiClient.post("/api/trasladar_varios", {
          productos: this.productosATrasladar,
        });
        alert(`Traslado realizado con consecutivo: ${response.data.consecutivo}`);
        this.productosATrasladar = [];
      } catch (error) {
        console.error("Error al confirmar traslado:", error);
        if (error.response && error.response.data && error.response.data.error) {
          // Mostrar mensaje de error detallado del backend
          alert(error.response.data.error);
        } else {
          alert("Ocurrió un error al realizar el traslado.");
        }
      }
    },
    async consultarTraslados() {
      try {
        const params = {
          consecutivo: this.filtroConsecutivo || undefined,
          codigo: this.filtroProducto || undefined,
          fecha_inicio: this.fechaInicio || undefined,
          fecha_fin: this.fechaFin || undefined,
          bodega_origen: this.filtroBodegaOrigen || undefined,
          bodega_destino: this.filtroBodegaDestino || undefined,
        };
        console.log("Parámetros enviados al backend:", params);
        const response = await apiClient.get("/api/traslados-por-bodega", { params }); // Nuevo endpoint

        // Eliminar duplicados por consecutivo
        const uniqueTraslados = [];
        const seenConsecutivos = new Set();
        response.data.forEach(item => {
          if (!seenConsecutivos.has(item.consecutivo)) {
            seenConsecutivos.add(item.consecutivo);
            uniqueTraslados.push({
              consecutivo: item.consecutivo,
              fecha: item.fecha
            });
          }
        });
        this.traslados = uniqueTraslados;

        this.detalleTraslado = [];
      } catch (error) {
        console.error("Error al consultar traslados:", error);
        alert("Ocurrió un error al consultar los traslados.");
      }
    },
    async verDetalleTraslado(consecutivo) {
      try {
        this.trasladoSeleccionado = consecutivo;
        const response = await apiClient.get("/api/traslados", {
          params: { consecutivo }
        });
        this.detalleTraslado = response.data;
      } catch (error) {
        console.error("Error al obtener detalle del traslado:", error);
        alert("No se pudo recuperar el detalle del traslado.");
      }
    },
    async imprimirTrasladosPDF() {
      try {
        const params = {
          consecutivo: this.filtroConsecutivo || undefined,
          codigo: this.filtroProducto || undefined,
          fecha_inicio: this.fechaInicio || undefined,
          fecha_fin: this.fechaFin || undefined,
          bodega_origen: this.filtroBodegaOrigen || undefined,
          bodega_destino: this.filtroBodegaDestino || undefined,
        };
        const response = await apiClient.get("/api/traslados-pdf", {
          params,
          responseType: "blob",
        });

        const url = window.URL.createObjectURL(new Blob([response.data]));
        const link = document.createElement("a");
        link.href = url;
        link.setAttribute("download", `traslados_${this.fechaInicio || 'todos'}_al_${this.fechaFin || 'todos'}.pdf`);
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
      } catch (error) {
        console.error("Error al generar el PDF de traslados:", error);
        alert("No se pudo generar el PDF de traslados.");
      }
    },
    exportarTrasladosExcel() {
      if (!this.traslados.length) {
        alert("No hay datos para exportar a Excel.");
        return;
      }

      const worksheetData = [
        ["Traslados Realizados"],
        [`Rango de fecha: ${this.fechaInicio || 'Todos'} - ${this.fechaFin || 'Todos'}`],
        [`Bodega de Origen: ${this.filtroBodegaOrigen || 'Cualquiera'}`],
        [`Bodega de Destino: ${this.filtroBodegaDestino || 'Cualquiera'}`],
        [], // Línea en blanco
        ["Consecutivo", "Fecha"],
      ];

      this.traslados.forEach((traslado) => {
        worksheetData.push([
          traslado.consecutivo,
          traslado.fecha,
        ]);
      });

      const worksheet = XLSX.utils.aoa_to_sheet(worksheetData);
      const workbook = XLSX.utils.book_new();
      XLSX.utils.book_append_sheet(workbook, worksheet, "Traslados");
      XLSX.writeFile(workbook, `traslados_${this.fechaInicio || 'todos'}_al_${this.fechaFin || 'todos'}.xlsx`);
    },
    async imprimirDetalleTrasladoPDF() {
      try {
        const response = await apiClient.get(`/api/traslado-detalle-pdf/${this.trasladoSeleccionado}`, {
          responseType: "blob",
        });

        const url = window.URL.createObjectURL(new Blob([response.data]));
        const link = document.createElement("a");
        link.href = url;
        link.setAttribute("download", `traslado_${this.trasladoSeleccionado}.pdf`);
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
      } catch (error) {
        console.error("Error al generar el PDF del detalle del traslado:", error);
        alert("No se pudo generar el PDF del detalle del traslado.");
      }
    },
    exportarDetalleTrasladoExcel() {
      if (!this.detalleTraslado.length) {
        alert("No hay datos para exportar a Excel.");
        return;
      }

      const fechaTraslado = this.detalleTraslado[0].fecha;
      const worksheetData = [
        ["Traslado entre Bodegas"],
        [`Número Traslado: ${this.trasladoSeleccionado}`],
        [`Fecha del Traslado: ${fechaTraslado}`],
        [], // Línea en blanco
        ["Producto", "Cantidad", "Bodega Origen", "Bodega Destino"],
      ];

      this.detalleTraslado.forEach((item) => {
        worksheetData.push([
          item.producto,
          item.cantidad,
          item.bodega_origen,
          item.bodega_destino,
        ]);
      });

      const worksheet = XLSX.utils.aoa_to_sheet(worksheetData);
      const workbook = XLSX.utils.book_new();
      XLSX.utils.book_append_sheet(workbook, worksheet, "Detalle Traslado");
      XLSX.writeFile(workbook, `traslado_${this.trasladoSeleccionado}.xlsx`);
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
    sincronizarPorNombre() {
      const productoEncontrado = this.productos.find(p => 
        p.nombre.toLowerCase().includes(this.nombreConsulta.toLowerCase())
      );

      if (productoEncontrado) {
        this.productoConsulta = productoEncontrado.codigo;
        this.codigoConsulta = productoEncontrado.codigo;
      }
    },

    sincronizarPorNombreTraslado() {
      const productoEncontrado = this.productos.find(p => 
        p.nombre.toLowerCase().includes(this.nombreTraslado.toLowerCase())
      );
      if (productoEncontrado) {
        this.nuevoTraslado.codigo = productoEncontrado.codigo;
        this.codigoTraslado = productoEncontrado.codigo;
      } else {
        this.nuevoTraslado.codigo = ""; // Limpiar si no se encuentra
        this.codigoTraslado = "";
      }
    },

    sincronizarPorNombreEnTraslado(index) {
      const producto = this.productosATrasladar[index];
      const productoEncontrado = this.productos.find(p => 
        p.nombre.toLowerCase().includes(producto.nombreDigitado.toLowerCase())
      );

      if (productoEncontrado) {
        producto.codigo = productoEncontrado.codigo;
        producto.nombre = productoEncontrado.nombre;
      }
    },

    sincronizarCodigoConSelector() {
      const productoEncontrado = this.productos.find(p => p.codigo === this.codigoConsulta);
      if (productoEncontrado) {
        this.productoConsulta = productoEncontrado.codigo;
        this.nombreConsulta = productoEncontrado.nombre;
      }
    },

    sincronizarSelectorConCodigo() {
      const productoEncontrado = this.productos.find(p => p.codigo === this.productoConsulta);
      if (productoEncontrado) {
        this.codigoConsulta = productoEncontrado.codigo;
        this.nombreConsulta = productoEncontrado.nombre;
      }
    },

    sincronizarPorNombreTraslado() {
      const productoEncontrado = this.productos.find(p => 
        p.nombre.toLowerCase().includes(this.nombreTraslado.toLowerCase())
      );
      if (productoEncontrado) {
        this.nuevoTraslado.codigo = productoEncontrado.codigo;
        this.codigoTraslado = productoEncontrado.codigo;
      } else {
        this.nuevoTraslado.codigo = ""; // Limpiar si no se encuentra
        this.codigoTraslado = "";
      }
    },

    sincronizarCodigoConSelectorTraslado() {
      const productoEncontrado = this.productos.find(p => p.codigo === this.codigoTraslado);
      if (productoEncontrado) {
        this.nuevoTraslado.codigo = productoEncontrado.codigo;
        this.nombreTraslado = productoEncontrado.nombre;
      } else {
        this.nuevoTraslado.codigo = ""; // Limpiar si no se encuentra
        this.nombreTraslado = "";
      }
    },

    sincronizarSelectorConCodigoTraslado() {
      const productoEncontrado = this.productos.find(p => p.codigo === this.nuevoTraslado.codigo);
      if (productoEncontrado) {
        this.nombreTraslado = productoEncontrado.nombre;
        this.codigoTraslado = productoEncontrado.codigo;
      } else {
        this.nombreTraslado = "";
        this.codigoTraslado = "";
      }
    },

    sincronizarPorNombreTraslados() {
      const productoEncontrado = this.productos.find(p => 
        p.nombre.toLowerCase().includes(this.nombreConsultaTraslados.toLowerCase())
      );

      if (productoEncontrado) {
        this.filtroProducto = productoEncontrado.codigo;
        this.codigoConsultaTraslados = productoEncontrado.codigo;
      }
    },

    sincronizarCodigoConSelectorTraslados() {
      const productoEncontrado = this.productos.find(p => p.codigo === this.codigoConsultaTraslados);
      if (productoEncontrado) {
        this.filtroProducto = productoEncontrado.codigo;
        this.nombreConsultaTraslados = productoEncontrado.nombre;
      }
    },

    sincronizarSelectorConCodigoTraslados() {
      const productoEncontrado = this.productos.find(p => p.codigo === this.filtroProducto);
      if (productoEncontrado) {
        this.codigoConsultaTraslados = productoEncontrado.codigo;
        this.nombreConsultaTraslados = productoEncontrado.nombre;
      }
    },

  },
  mounted() {
    this.cargarProductos();
    this.cargarBodegas();
  },
};
</script>

<style scoped>
/* Estilo general del contenedor */
.trasladar-cantidades {
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
.form-group {
  margin-bottom: 15px;
}

label {
  font-weight: bold;
  display: block;
  margin-bottom: 5px;
  color: #555;
}

input, select {
  width: 100%;
  padding: 10px;
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

/* Responsividad */
@media (max-width: 768px) {
  .trasladar-cantidades {
    margin: 10px auto;
    padding: 10px;
  }

  input, select, button {
    width: 100%;
    margin-bottom: 10px;
    font-size: 16px;
  }

  table {
    display: block;
    overflow-x: auto;
    white-space: nowrap;
  }

  th, td {
    font-size: 12px;
    padding: 8px;
  }

  h1 {
    font-size: 20px;
  }

  h2, h3 {
    font-size: 18px;
  }
}
</style>




