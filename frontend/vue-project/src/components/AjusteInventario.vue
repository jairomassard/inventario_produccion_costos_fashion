<template>
  <div>
    <h1>Ajuste Manual de Inventario</h1>

    <div>
      <button @click="volverAlMenu" class="btn btn-secondary">Volver al Menú Principal</button>
      <button @click="limpiarPagina" class="btn btn-warning">Limpiar Página</button>
    </div>

    <!-- Sección de Realización de ajustes de Inventario Manual -->
    <section>
      <h2>Realizar Ajuste Manual de Inventario</h2>
      <div>
        <label for="nombreFiltro">Buscar por nombre:</label>
        <input 
          type="text" 
          id="nombreFiltro"
          v-model="nombreDigitado"
          placeholder="Ingrese nombre del producto"
          class="form-control"
          @input="sincronizarPorNombre"
        />

        <label for="codigoFiltro">Buscar por código:</label>
        <input 
          v-model="codigoDigitado" 
          id="codigoFiltro" 
          placeholder="Ingrese código de producto" 
          class="form-control"
          @input="sincronizarCodigoConSelector"
        />

        <label for="productoSelector">Seleccione un producto:</label>
        <select v-model="filtroProducto" id="productoSelector" @change="sincronizarSelectorConCodigo">
          <option value="" disabled>Seleccione un producto</option>
          <option v-for="producto in productosDisponibles" :key="producto.codigo" :value="producto.codigo">
            {{ producto.codigo }} - {{ producto.nombre }}
          </option>
        </select>

        <button @click="consultar">Consultar Inventario</button>
      </div>
    </section>

    <!-- Tabla de Inventario -->
    <section v-if="mostrarInventario">
      <h2>Inventario Disponible</h2>
      <table>
        <thead>
          <tr>
            <th>Código</th>
            <th>Nombre</th>
            <th>Total</th>
            <th v-for="bodega in bodegas" :key="bodega">{{ bodega }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="producto in productos" :key="producto.codigo">
            <td>{{ producto.codigo }}</td>
            <td>{{ producto.nombre }}</td>
            <td>{{ producto.cantidad_total }}</td>
            <td v-for="bodega in bodegas" :key="bodega">
              {{ producto.cantidades_por_bodega[bodega] || 0 }}
            </td>
          </tr>
        </tbody>
      </table>
    </section>

    <!-- Formulario de Ajuste de Inventario -->
    <section v-if="mostrarInventario">
      <h3>Ajuste de Inventario</h3>
      <label for="bodegaSelector">Seleccione la bodega:</label>
      <select v-model="bodegaSeleccionada" id="bodegaSelector">
        <option value="" disabled>Seleccione una bodega</option>
        <option v-for="bodega in bodegas" :key="bodega" :value="bodega">{{ bodega }}</option>
      </select>

      <label for="accionSelector">Acción:</label>
      <select v-model="accionSeleccionada" id="accionSelector">
        <option value="Incrementar">Incrementar</option>
        <option value="Disminuir">Disminuir</option>
      </select>

      <label for="cantidadAjuste">Cantidad:</label>
      <input v-model.number="cantidadAjuste" id="cantidadAjuste" type="number" min="1" />

      <button @click="agregarProductoAjuste">Agregar Producto</button>
    </section>

    <!-- Tabla de Productos en Ajuste -->
    <section v-if="productosEnAjuste.length">
      <h3>Productos a Ajustar</h3>
      <table>
        <thead>
          <tr>
            <th>Código</th>
            <th>Nombre</th>
            <th>Bodega</th>
            <th>Acción</th>
            <th>Cantidad</th>
            <th>Acciones</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(producto, index) in productosEnAjuste" :key="index">
            <td>{{ producto.codigo }}</td>
            <td>{{ producto.nombre }}</td>
            <td>{{ producto.bodega }}</td>
            <td>{{ producto.accion }}</td>
            <td>{{ producto.cantidad }}</td>
            <td>
              <button @click="eliminarProductoAjuste(index)" class="btn btn-danger">Eliminar</button>
            </td>
          </tr>
        </tbody>
      </table>
      <button @click="realizarAjuste" class="btn btn-primary">Realizar Ajuste</button>
    </section>

    <!-- Sección de Consulta de Ajustes de Inventario -->
    <section>
      <h2>Consulta de Ajustes de Inventario</h2>
      <label for="filtroTransaccion">Número de Transacción:</label>
      <input v-model="filtroTransaccion" id="filtroTransaccion" placeholder="Ingrese número de transacción" />

      <label for="fechaInicio">Fecha Inicio:</label>
      <input type="date" v-model="fechaInicio" id="fechaInicio" />

      <label for="fechaFin">Fecha Fin:</label>
      <input type="date" v-model="fechaFin" id="fechaFin" />

      <p class="info-message">
        Nota: Para incluir movimientos del día actual, seleccione un día adicional como fecha final.
      </p>

      <button @click="consultarAjustes">Buscar Ajustes</button>
    </section>

    <!-- Tabla de Ajustes de Inventario -->
    <section v-if="ajustes.length">
      <h2>Resultados de Ajustes</h2>
      <div>
        <button @click="imprimirAjustes_listadoPDF" class="btn btn-success">Imprimir Listado <i class="fas fa-file-pdf pdf-icon"></i></button>
        <button @click="exportarAjustes_listadoExcel" class="btn btn-primary">Exportar Listado <i class="fas fa-file-excel excel-icon"></i></button>
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
          <tr v-for="ajuste in ajustes" :key="ajuste.consecutivo">
            <td>{{ ajuste.consecutivo }}</td>
            <td>{{ ajuste.fecha }}</td>
            <td>
              <button @click="verDetalle(ajuste.consecutivo)" class="btn btn-info">Detalle</button>
            </td>
          </tr>
        </tbody>
      </table>
    </section>

    <!-- Detalles del Ajuste Seleccionado -->
    <section v-if="detalleAjuste.length">
      <h2>Detalle del Ajuste {{ ajusteSeleccionado }}</h2>
      <div>
        <button @click="imprimirAjustePDF" class="btn btn-success">Imprimir <i class="fas fa-file-pdf pdf-icon"></i></button>
        <button @click="exportarAjusteExcel" class="btn btn-primary">Exportar <i class="fas fa-file-excel excel-icon"></i></button>
      </div>
      <table>
        <thead>
          <tr>
            <th>Código</th>
            <th>Nombre Producto</th>
            <th>Bodega</th>
            <th>Cantidad Anterior</th>
            <th>Acción</th>
            <th>Cantidad Ajustada</th>
            <th>Cantidad Final</th>
            <th>Costo Unitario</th>
            <th>Costo Total</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="detalle in detalleAjuste" :key="detalle.id">
            <td>{{ detalle.codigo_producto }}</td>
            <td>{{ detalle.nombre_producto }}</td>
            <td>{{ detalle.bodega_nombre }}</td>
            <td>{{ detalle.cantidad_anterior }}</td>
            <td>{{ detalle.tipo_movimiento }}</td>
            <td>{{ detalle.cantidad_ajustada }}</td>
            <td>{{ detalle.cantidad_final }}</td>
            <td>{{ detalle.costo_unitario ? `$${detalle.costo_unitario.toFixed(2)}` : 'N/A' }}</td>
            <td>{{ detalle.costo_total ? `$${detalle.costo_total.toFixed(2)}` : 'N/A' }}</td>
          </tr>
        </tbody>
      </table>
      <button @click="limpiarPagina" class="btn btn-warning">Limpiar Página</button>
    </section>
  </div>
</template>

<script>
import apiClient from "../services/axios";
import * as XLSX from "xlsx";

export default {
  name: "AjusteInventario",
  data() {
    return {
      filtroProducto: "",
      filtroTransaccion: "",
      fechaInicio: "",
      fechaFin: "",
      ajustes: [],
      detalleAjuste: [],
      ajusteSeleccionado: "",
      fechaAjuste: "",
      codigoDigitado: "",
      nombreDigitado: "",
      productosDisponibles: [],
      productos: [],
      bodegas: [],
      mostrarInventario: false,
      bodegaSeleccionada: "",
      accionSeleccionada: "Incrementar",
      cantidadAjuste: 1,
      productosEnAjuste: [],
    };
  },
  methods: {
    async cargarProductosDisponibles() {
      try {
        const response = await apiClient.get("/api/productos/completos");
        this.productosDisponibles = response.data
          .sort((a, b) => a.codigo.localeCompare(b.codigo));
      } catch (error) {
        console.error("Error al cargar productos disponibles:", error);
      }
    },
    async consultar() {
      try {
        const codigo = this.codigoDigitado || this.filtroProducto;
        if (!codigo) {
          alert("Seleccione o escriba un producto para consultar.");
          return;
        }

        const response = await apiClient.get(`/api/inventario/${codigo}`);
        const { producto, inventario } = response.data;
        const bodegasResponse = await apiClient.get("/api/bodegas");
        this.bodegas = bodegasResponse.data.map((b) => b.nombre);

        this.productos = [
          {
            codigo: producto.codigo,
            nombre: producto.nombre,
            cantidad_total: inventario.reduce((total, item) => total + item.cantidad, 0),
            cantidades_por_bodega: Object.fromEntries(inventario.map(i => [i.bodega, i.cantidad]))
          },
        ];
        this.mostrarInventario = true;
      } catch (error) {
        console.error("Error al consultar inventario:", error);
        alert("Ocurrió un error al consultar el inventario.");
      }
    },
    sincronizarCodigoConSelector() {
      const productoEncontrado = this.productosDisponibles.find(
        (p) => p.codigo === this.codigoDigitado
      );
      if (productoEncontrado) {
        this.filtroProducto = productoEncontrado.codigo;
      }
    },
    sincronizarSelectorConCodigo() {
      const productoSeleccionado = this.productosDisponibles.find(
        (p) => p.codigo === this.filtroProducto
      );
      if (productoSeleccionado) {
        this.codigoDigitado = productoSeleccionado.codigo;
      }
    },
    agregarProductoAjuste() {
      const codigoSeleccionado = this.codigoDigitado.trim() || this.filtroProducto;

      if (!codigoSeleccionado || !this.bodegaSeleccionada || !this.accionSeleccionada || !this.cantidadAjuste) {
        alert("Seleccione un producto, bodega, tipo de movimiento y cantidad válida.");
        return;
      }

      const producto = this.productosDisponibles.find(p => p.codigo === codigoSeleccionado);
      if (!producto) {
        alert("Producto no encontrado. Asegúrese de haber consultado el inventario antes de agregarlo.");
        return;
      }

      this.productosEnAjuste.push({
        codigo: producto.codigo,
        nombre: producto.nombre,
        bodega: this.bodegaSeleccionada,
        accion: this.accionSeleccionada,
        cantidad: this.cantidadAjuste
      });

      this.filtroProducto = "";
      this.codigoDigitado = "";
      this.accionSeleccionada = "Incrementar";
      this.cantidadAjuste = 1;
    },
    eliminarProductoAjuste(index) {
      this.productosEnAjuste.splice(index, 1);
    },
    async realizarAjuste() {
      try {
        if (!this.bodegaSeleccionada) {
          alert("Seleccione una bodega para realizar el ajuste.");
          return;
        }
        if (this.productosEnAjuste.length === 0) {
          alert("Agregue al menos un producto para ajustar.");
          return;
        }

        const productosParaAjuste = this.productosEnAjuste.map(producto => ({
          codigoProducto: producto.codigo,
          tipoMovimiento: producto.accion,
          nuevaCantidad: producto.cantidad
        }));

        const usuario_id = localStorage.getItem("usuario_id");
        if (!usuario_id) {
          alert("No se pudo identificar al usuario. Por favor, inicia sesión nuevamente.");
          return;
        }

        const response = await apiClient.post("/api/ajuste-inventario", {
          bodega: this.bodegaSeleccionada,
          productos: productosParaAjuste,
          usuario_id: usuario_id
        });

        alert(`Ajuste realizado con éxito. Consecutivo: ${response.data.consecutivo}`);

        const codigoProductoConsultado = this.filtroProducto || this.codigoDigitado;
        this.productosEnAjuste = [];
        this.filtroProducto = "";
        this.codigoDigitado = "";
        this.bodegaSeleccionada = "";
        this.accionSeleccionada = "Incrementar";
        this.cantidadAjuste = 1;
        this.mostrarInventario = false;

        if (codigoProductoConsultado) {
          this.consultar();
        }
      } catch (error) {
        console.error("Error al realizar ajuste:", error);
        alert("No se pudo completar el ajuste de inventario.");
      }
    },
    async consultarAjustes() {
      try {
        if (!this.filtroTransaccion && (!this.fechaInicio || !this.fechaFin)) {
          alert("Ingrese un número de transacción o un rango de fechas.");
          return;
        }

        const params = {};
        if (this.filtroTransaccion) params.consecutivo = this.filtroTransaccion;
        if (this.fechaInicio && this.fechaFin) {
          params.fechaInicio = this.fechaInicio;
          params.fechaFin = this.fechaFin;
        }

        const response = await apiClient.get("/api/consulta-ajustes", { params });
        this.ajustes = response.data;
      } catch (error) {
        console.error("Error al consultar ajustes:", error);
        alert("No se pudo recuperar la información.");
      }
    },
    async verDetalle(consecutivo) {
      try {
        this.ajusteSeleccionado = consecutivo;

        const detalleResponse = await apiClient.get(`/api/ajuste-detalle/${consecutivo}`);
        this.detalleAjuste = detalleResponse.data;

        const consultaResponse = await apiClient.get("/api/consulta-ajustes", {
          params: { consecutivo },
        });
        const ajuste = consultaResponse.data.find(a => a.consecutivo === consecutivo);
        this.fechaAjuste = ajuste ? ajuste.fecha : "Desconocida";
      } catch (error) {
        console.error("Error al obtener detalles del ajuste:", error);
        alert("No se pudo recuperar la información del ajuste.");
      }
    },
    async imprimirAjustes_listadoPDF() {
      try {
        if (!this.fechaInicio || !this.fechaFin) {
          alert("Por favor, especifique un rango de fechas para imprimir.");
          return;
        }

        const response = await apiClient.get("/api/consultaListado-ajustes-pdf", {
          params: {
            fechaInicio: this.fechaInicio,
            fechaFin: this.fechaFin,
          },
          responseType: "blob",
        });

        const url = window.URL.createObjectURL(new Blob([response.data]));
        const link = document.createElement("a");
        link.href = url;
        link.setAttribute("download", `ajustes_${this.fechaInicio}_al_${this.fechaFin}.pdf`);
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
      } catch (error) {
        console.error("Error al generar el PDF de ajustes:", error);
        alert("No se pudo generar el PDF de ajustes.");
      }
    },
    async imprimirAjustePDF() {
      try {
        const response = await apiClient.get(`/api/ajuste-detalle-pdf/${this.ajusteSeleccionado}`, {
          responseType: "blob",
        });

        const url = window.URL.createObjectURL(new Blob([response.data]));
        const link = document.createElement("a");
        link.href = url;
        link.setAttribute("download", `ajuste_${this.ajusteSeleccionado}.pdf`);
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
      } catch (error) {
        console.error("Error al generar el PDF del ajuste:", error);
        alert("No se pudo generar el PDF del ajuste.");
      }
    },
    exportarAjustes_listadoExcel() {
      if (!this.ajustes.length) {
        alert("No hay datos para exportar a Excel.");
        return;
      }

      if (!this.fechaInicio || !this.fechaFin) {
        alert("Por favor, especifique un rango de fechas para exportar.");
        return;
      }

      const worksheetData = [
        ["Ajustes de Inventario Realizados"],
        [`Rango de fecha: ${this.fechaInicio} - ${this.fechaFin}`],
        [],
        ["Consecutivo", "Fecha"],
      ];

      this.ajustes.forEach((ajuste) => {
        worksheetData.push([
          ajuste.consecutivo,
          ajuste.fecha,
        ]);
      });

      const worksheet = XLSX.utils.aoa_to_sheet(worksheetData);
      const workbook = XLSX.utils.book_new();
      XLSX.utils.book_append_sheet(workbook, worksheet, "Ajustes");
      XLSX.writeFile(workbook, `Listado_ajustes_${this.fechaInicio}_al_${this.fechaFin}.xlsx`);
    },
    exportarAjusteExcel() {
      if (!this.detalleAjuste.length) {
        alert("No hay datos para exportar a Excel.");
        return;
      }

      const nombres = localStorage.getItem("nombres") || "Desconocido";
      const apellidos = localStorage.getItem("apellidos") || "";
      const usuario = `${nombres} ${apellidos}`.trim();
      const fechaAjuste = this.fechaAjuste || "Desconocida";

      const worksheetData = [
        ["Ajuste de Inventario"],
        [`Detalle del Ajuste ${this.ajusteSeleccionado}`],
        [`Fecha Realización: ${fechaAjuste}`],
        [`Realizado por: ${usuario}`],
        [],
        ["Código", "Nombre Producto", "Bodega", "Cantidad Anterior", "Acción", "Cantidad Ajustada", "Cantidad Final", "Costo Unitario", "Costo Total"],
      ];

      this.detalleAjuste.forEach((detalle) => {
        worksheetData.push([
          detalle.codigo_producto,
          detalle.nombre_producto,
          detalle.bodega_nombre,
          detalle.cantidad_anterior,
          detalle.tipo_movimiento,
          detalle.cantidad_ajustada,
          detalle.cantidad_final,
          detalle.costo_unitario ? detalle.costo_unitario.toFixed(2) : "N/A",
          detalle.costo_total ? detalle.costo_total.toFixed(2) : "N/A",
        ]);
      });

      const worksheet = XLSX.utils.aoa_to_sheet(worksheetData);
      const workbook = XLSX.utils.book_new();
      XLSX.utils.book_append_sheet(workbook, worksheet, "Ajuste");
      XLSX.writeFile(workbook, `ajuste_${this.ajusteSeleccionado}.xlsx`);
    },
    sincronizarPorNombre() {
      const productoEncontrado = this.productosDisponibles.find(p => 
        p.nombre.toLowerCase().includes(this.nombreDigitado.toLowerCase())
      );

      if (productoEncontrado) {
        this.filtroProducto = productoEncontrado.codigo;
        this.codigoDigitado = productoEncontrado.codigo;
      }
    },
    sincronizarCodigoConSelector() {
      const productoEncontrado = this.productosDisponibles.find(p => p.codigo === this.codigoDigitado);
      if (productoEncontrado) {
        this.filtroProducto = productoEncontrado.codigo;
        this.nombreDigitado = productoEncontrado.nombre;
      }
    },
    sincronizarSelectorConCodigo() {
      const productoSeleccionado = this.productosDisponibles.find(p => p.codigo === this.filtroProducto);
      if (productoSeleccionado) {
        this.codigoDigitado = productoSeleccionado.codigo;
        this.nombreDigitado = productoSeleccionado.nombre;
      }
    },
    limpiarPagina() {
      this.codigoDigitado = "";
      this.nombreDigitado = "";
      this.filtroProducto = "";
      this.mostrarInventario = false;
      this.bodegaSeleccionada = "";
      this.accionSeleccionada = "Incrementar";
      this.cantidadAjuste = 1;
      this.productosEnAjuste = [];
      this.filtroTransaccion = "";
      this.fechaInicio = "";
      this.fechaFin = "";
      this.ajustes = [];
      this.detalleAjuste = [];
      this.ajusteSeleccionado = "";
      this.cargarProductosDisponibles();
    },
    volverAlMenu() {
      const tipoUsuario = localStorage.getItem("tipo_usuario");
      const rutas = {
        admin: "/menu",
        gerente: "/menu-gerente",
        operador: "/menu-operador",
      };
      this.$router.push(rutas[tipoUsuario] || "/");
    },
  },
  mounted() {
    this.cargarProductosDisponibles();
  },
};
</script>
  
  <style scoped>
  /* Contenedor principal */
  div {
    margin: 20px auto;
    max-width: 1200px;
    font-family: Arial, sans-serif;
    padding: 10px;
  }
  
  /* Títulos */
  h1 {
    text-align: center;
    color: #333; /* Texto oscuro */
    margin-bottom: 20px;
  }
  
  h2, h3 {
    color: #0056b3; /* Azul para subtítulos */
    margin-bottom: 15px;
  }
  
  /* Botones */
  button {
    padding: 0.6rem 1.2rem;
    border: none;
    background-color: #007bff; /* Azul para botones */
    color: #fff; /* Texto blanco */
    cursor: pointer;
    border-radius: 4px;
    font-size: 14px;
    margin-right: 10px;
    transition: background-color 0.3s ease, transform 0.2s ease;
  }
  
  button:hover {
    background-color: #0056b3; /* Azul más oscuro */
    transform: translateY(-2px); /* Efecto de elevación */
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.15); /* Sombra ligera */
  }
  
  button.btn-warning {
    background-color: #ffc107; /* Amarillo para advertencias */
    color: #333; /* Texto oscuro */
  }
  
  button.btn-warning:hover {
    background-color: #e0a800; /* Amarillo más oscuro */
  }
  
  /* Formularios y Selectores */
  label {
    font-weight: bold;
    display: block;
    margin-bottom: 5px;
    color: #555; /* Texto gris */
  }
  
  select, input[type="number"], input[type="text"] {
    width: 100%;
    padding: 10px;
    margin-bottom: 15px;
    border: 1px solid #ccc; /* Borde gris */
    border-radius: 4px;
    font-size: 14px;
    box-sizing: border-box;
    background-color: #fff; /* Fondo blanco */
    color: #333; /* Texto oscuro */
    transition: border-color 0.3s ease-in-out;
  }
  
  select:focus, input:focus {
    border-color: #007bff; /* Azul en foco */
    outline: none;
    box-shadow: 0 0 4px rgba(0, 123, 255, 0.25); /* Sombra azul ligera */
  }
  
  option {
    color: #333; /* Texto oscuro */
    background-color: #fff; /* Fondo blanco */
  }
  
  /* Formulario de ajuste */
  .ajuste-form {
    margin-top: 20px;
    padding: 15px;
    border: 1px solid #e0e0e0;
    border-radius: 6px;
    background-color: #f8f9fa; /* Fondo gris claro */
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
    background-color: #f8f9fa; /* Fondo gris claro */
    color: #333; /* Texto oscuro */
    font-weight: bold;
  }
  
  tbody tr:nth-child(odd) {
    background-color: #f9f9f9; /* Fondo gris claro para filas impares */
  }
  
  tbody tr:hover {
    background-color: #f1f1f1; /* Fondo más claro al pasar el cursor */
  }
  
  /* Secciones */
  section {
    margin-bottom: 30px;
    padding: 15px;
    border: 1px solid #e9ecef;
    border-radius: 6px;
    background-color: #f8f9fa; /* Fondo gris claro */
  }
  
  /* Historial de mensajes */
  p {
    margin: 5px 0;
    color: #555; /* Texto gris */
    font-size: 14px;
  }
  
  /* Responsividad */
  @media (max-width: 768px) {
    /* Reducir márgenes en pantallas pequeñas */
    div {
      margin: 10px auto;
      padding: 10px;
    }
  
    /* Formularios en columna */
    select, input, button {
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
  </style>
  
  
  
  
  
  
  