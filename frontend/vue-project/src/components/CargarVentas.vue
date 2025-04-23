<template>
  <div class="cargar-ventas">
    <h1>Cargar Ventas</h1>

    <section class="menu-buttons">
      <button @click="volverAlMenu" class="btn btn-secondary" :disabled="isLoading">Volver al Menú Principal</button>
      <button @click="limpiarPagina" class="btn btn-warning" :disabled="isLoading">Limpiar Página</button>
    </section>

    <!-- Subida de Archivo CSV -->
    <section>
      <h2>Subir Archivo CSV</h2>
      <div>
        <label for="inputCsv">Archivo CSV:</label>
        <input id="inputCsv" type="file" @change="cargarCsv" class="form-control" :disabled="isLoading" />
      </div>
      <button @click="procesarCsv" :disabled="isLoading" class="btn btn-primary">
        {{ isLoading ? 'Procesando...' : 'Cargar Ventas' }}
      </button>
      <div v-if="isLoading" class="spinner">
        <div class="spinner-icon"></div>
        <p>Procesando archivo, por favor espera...</p>
      </div>
    </section>

    <!-- Mostrar errores -->
    <section v-if="errores.length">
      <h2>Errores detectados:</h2>
      <ul>
        <li v-for="(error, index) in errores" :key="index">{{ error }}</li>
      </ul>
    </section>

    <!-- Descarga de Plantilla -->
    <section>
      <h2>Descargar Plantilla</h2>
      <button @click="descargarPlantilla" :disabled="isLoading" class="btn btn-primary">Descargar</button>
    </section>

    <!-- Consulta de Facturas de Venta -->
    <section class="consulta-ventas">
      <h2>Consulta de Facturas de Venta</h2>
      <div>
        <label for="filtroFactura">Número de Factura:</label>
        <input
          v-model="filtroFactura"
          id="filtroFactura"
          placeholder="Ingrese número de factura"
          class="form-control"
          :disabled="isLoading"
        />
      </div>
      <div>
        <label for="fechaInicio">Fecha Inicio:</label>
        <input type="date" v-model="fechaInicio" id="fechaInicio" class="form-control" :disabled="isLoading" />
      </div>
      <div>
        <label for="fechaFin">Fecha Fin:</label>
        <input type="date" v-model="fechaFin" id="fechaFin" class="form-control" :disabled="isLoading" />
      </div>
      <div>
        <label for="filtroBodega">Bodega de Venta:</label>
        <select v-model="filtroBodega" id="filtroBodega" class="form-control" :disabled="isLoading">
          <option value="" disabled>Seleccione una bodega</option>
          <option v-for="bodega in bodegas" :key="bodega.id" :value="bodega.id">{{ bodega.nombre }}</option>
        </select>
      </div>
      <div>
        <label for="selectorFactura">Seleccionar Factura:</label>
        <select v-model="filtroFactura" id="selectorFactura" class="form-control" :disabled="isLoading">
          <option value="" disabled>Seleccione una factura</option>
          <option v-for="factura in facturas" :key="factura" :value="factura">{{ factura }}</option>
        </select>
      </div>
      <button @click="consultarVentas" :disabled="isLoading" class="btn btn-primary">Consultar Facturas</button>
    </section>

    <!-- Resultados de la Consulta -->
    <section v-if="resultadosVentas.length" class="resultados-ventas">
      <h3>Resultados de la Consulta</h3>
      <div>
        <button @click="exportarListadoExcel" class="btn btn-primary" :disabled="isLoading">
          Exportar Listado <i class="fas fa-file-excel excel-icon"></i>
        </button>
      </div>
      <table>
        <thead>
          <tr>
            <th>Número de Factura</th>
            <th>Fecha y Hora</th>
            <th>Acción</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="venta in resultadosVentas" :key="venta.factura">
            <td>{{ venta.factura }}</td>
            <td>{{ venta.fecha }}</td>
            <td>
              <button @click="verDetalleVenta(venta.factura)" class="btn btn-info" :disabled="isLoading">Detalle</button>
            </td>
          </tr>
        </tbody>
      </table>
    </section>

    <!-- Detalle de la Factura de Venta -->
    <section v-if="detalleVenta.length" class="detalle-venta">
      <h3>Detalle de la Factura de Venta {{ facturaSeleccionada }}</h3>
      <div>
        <button @click="exportarDetalleExcel" class="btn btn-primary" :disabled="isLoading">
          Exportar <i class="fas fa-file-excel excel-icon"></i>
        </button>
      </div>
      <table>
        <thead>
          <tr>
            <th>Código</th>
            <th>Nombre</th>
            <th>Cantidad</th>
            <th>Bodega de Venta</th>
            <th>Precio Unitario</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in detalleVenta" :key="item.id">
            <td>{{ item.codigo }}</td>
            <td>{{ item.nombre }}</td>
            <td>{{ item.cantidad }}</td>
            <td>{{ item.bodega }}</td>
            <td>{{ item.precio_unitario !== null ? `$${item.precio_unitario.toFixed(2)}` : 'N/A' }}</td>
          </tr>
        </tbody>
      </table>
    </section>
  </div>
</template>

<script>
import apiClient from "../services/axios";
import * as XLSX from "xlsx";

export default {
  name: "CargarVentas",
  data() {
    return {
      archivoCsv: null,
      errores: [],
      filtroFactura: "",
      fechaInicio: "",
      fechaFin: "",
      filtroBodega: "",
      facturas: [],
      bodegas: [],
      resultadosVentas: [],
      detalleVenta: [],
      facturaSeleccionada: "",
      isLoading: false, // Controla el estado de carga
    };
  },
  methods: {
    cargarCsv(event) {
      this.archivoCsv = event.target.files[0];
    },
    async procesarCsv() {
      if (!this.archivoCsv) {
        alert("Seleccione un archivo para cargar");
        return;
      }

      this.isLoading = true; // Activar spinner
      this.errores = [];

      const formData = new FormData();
      formData.append("file", this.archivoCsv);

      try {
        const response = await apiClient.post("/api/ventas", formData, {
          headers: {
            "Content-Type": "multipart/form-data",
          },
        });
        alert(response.data.message);
        this.cargarFacturas();
      } catch (error) {
        console.error("Error al cargar ventas:", error);
        if (error.response && error.response.data.errors) {
          this.errores = error.response.data.errors;
        } else {
          this.errores = ["Ocurrió un error al cargar las ventas sin detalles específicos"];
        }
      } finally {
        this.isLoading = false; // Desactivar spinner
      }
    },
    descargarPlantilla() {
      const csvData = [
        ["factura", "codigo", "nombre", "cantidad", "fecha_venta", "bodega", "precio_unitario"],
        ["FB1234567", "GRA05299901000000", "R5 BULK PASTEL YELLOW", "10", "2025-04-05 10:00:00", "Bodega1", "75.00"],
        ["CC8901234", "GRA05299909000000", "R5 BULK PASTEL LIGTH PINK", "5", "2025-04-05 11:30:00", "Bodega2", ""],
      ];
      const csvContent =
        "data:text/csv;charset=utf-8," +
        csvData.map((e) => e.join(",")).join("\n");
      const encodedUri = encodeURI(csvContent);
      const link = document.createElement("a");
      link.setAttribute("href", encodedUri);
      link.setAttribute("download", "plantilla_cargue_ventas.csv");
      document.body.appendChild(link);
      link.click();
    },
    volverAlMenu() {
      const tipoUsuario = localStorage.getItem("tipo_usuario");
      if (tipoUsuario === "admin") {
        this.$router.push('/menu');
      } else if (tipoUsuario === "gerente") {
        this.$router.push('/menu-gerente');
      } else {
        alert("Rol no reconocido. Contacta al administrador.");
      }
    },
    limpiarPagina() {
      this.archivoCsv = null;
      this.errores = [];
      this.filtroFactura = "";
      this.fechaInicio = "";
      this.fechaFin = "";
      this.filtroBodega = "";
      this.resultadosVentas = [];
      this.detalleVenta = [];
      this.facturaSeleccionada = "";
      this.isLoading = false;
    },
    async cargarFacturas() {
      try {
        const response = await apiClient.get("/api/ventas_facturas");
        this.facturas = response.data.facturas;
      } catch (error) {
        console.error("Error al cargar facturas:", error);
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
    async consultarVentas() {
      try {
        const params = {
          factura: this.filtroFactura || undefined,
          fecha_inicio: this.fechaInicio || undefined,
          fecha_fin: this.fechaFin || undefined,
          bodega_id: this.filtroBodega || undefined,
        };
        const response = await apiClient.get("/api/consultar_ventas", { params });
        this.resultadosVentas = response.data;
        this.detalleVenta = [];
      } catch (error) {
        console.error("Error al consultar facturas de venta:", error);
        alert("Ocurrió un error al consultar las facturas.");
      }
    },
    async verDetalleVenta(factura) {
      try {
        this.facturaSeleccionada = factura;
        const response = await apiClient.get("/api/detalle_venta", {
          params: { factura: factura }
        });
        this.detalleVenta = response.data;
      } catch (error) {
        console.error("Error al obtener detalle de la factura:", error);
        alert("No se pudo recuperar el detalle de la factura.");
      }
    },
    exportarListadoExcel() {
      if (!this.resultadosVentas.length) {
        alert("No hay datos para exportar a Excel.");
        return;
      }

      const worksheetData = [
        ["Resultado de consulta de Factura de Ventas Cargadas"],
        [`Número de Factura: ${this.filtroFactura || 'Todos'}`],
        [`Fecha Inicio: ${this.fechaInicio || 'No especificada'}`],
        [`Fecha Fin: ${this.fechaFin || 'No especificada'}`],
        [`Bodega: ${this.bodegas.find(b => b.id === this.filtroBodega)?.nombre || 'Todas'}`],
        [], // Línea en blanco
        ["Nombre de Factura", "Fecha y Hora"],
      ];

      this.resultadosVentas.forEach((venta) => {
        worksheetData.push([
          venta.factura,
          venta.fecha,
        ]);
      });

      const worksheet = XLSX.utils.aoa_to_sheet(worksheetData);
      const workbook = XLSX.utils.book_new();
      XLSX.utils.book_append_sheet(workbook, worksheet, "Facturas");
      XLSX.writeFile(workbook, `facturas_ventas_${new Date().toISOString().slice(0,10)}.xlsx`);
    },
    exportarDetalleExcel() {
      if (!this.detalleVenta.length) {
        alert("No hay datos para exportar a Excel.");
        return;
      }

      const fechaCargue = this.resultadosVentas.find(v => v.factura === this.facturaSeleccionada)?.fecha || "Desconocida";

      const worksheetData = [
        [`Detalle Factura ${this.facturaSeleccionada}`],
        [`Fecha de Cargue: ${fechaCargue}`],
        [], // Línea en blanco
        ["Código", "Nombre", "Cantidad", "Bodega de Venta", "Precio Unitario"],
      ];

      this.detalleVenta.forEach((item) => {
        worksheetData.push([
          item.codigo,
          item.nombre,
          item.cantidad,
          item.bodega,
          item.precio_unitario !== null ? item.precio_unitario.toFixed(2) : "N/A",
        ]);
      });

      const worksheet = XLSX.utils.aoa_to_sheet(worksheetData);
      const workbook = XLSX.utils.book_new();
      XLSX.utils.book_append_sheet(workbook, worksheet, "Detalle Factura");
      XLSX.writeFile(workbook, `detalle_factura_${this.facturaSeleccionada}.xlsx`);
    },
  },
  mounted() {
    this.cargarFacturas();
    this.cargarBodegas();
  },
};
</script>

<style scoped>
/* Contenedor principal */
.cargar-ventas {
  margin: 20px auto;
  max-width: 1200px;
  font-family: Arial, sans-serif;
  padding: 10px;
}
.excel-icon {
  font-size: 18px;
  vertical-align: middle;
  margin-left: 5px;
  color: #fff;
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
  transition: background-color 0.3s ease, transform 0.2s ease;
}
button:hover {
  background-color: #0056b3;
  transform: translateY(-2px);
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.15);
}
.btn-secondary {
  background-color: #007bff;
}
.btn-secondary:hover {
  background-color: #0056b3;
}
.btn-warning {
  background-color: #ffc107;
  color: #333;
}
.btn-warning:hover {
  background-color: #e0a800;
}
.btn-info {
  background-color: #007bff;
}
.btn-info:hover {
  background-color: #0056b3;
}
.btn-primary {
  background-color: #007bff;
}
.btn-primary:hover {
  background-color: #0056b3;
}
/* Formularios */
label {
  font-weight: bold;
  display: block;
  margin-bottom: 5px;
  color: #555;
}
input, select {
  width: 100%;
  padding: 10px;
  margin-bottom: 15px;
  border: 1px solid #ccc;
  border-radius: 4px;
  font-size: 14px;
  box-sizing: border-box;
  background-color: #fff;
  color: #333;
  transition: border-color 0.3s ease-in-out;
}
input:focus, select:focus {
  border-color: #007bff;
  outline: none;
  box-shadow: 0 0 4px rgba(0, 123, 255, 0.25);
}
/* Spinner */
.spinner {
  display: flex;
  align-items: center;
  margin-top: 10px;
}
.spinner-icon {
  width: 24px;
  height: 24px;
  border: 3px solid #ccc;
  border-top: 3px solid #007bff;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin-right: 10px;
}
@keyframes spin {
  to { transform: rotate(360deg); }
}
.spinner p {
  margin: 0;
  color: #555;
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
/* Menu buttons */
.menu-buttons {
  margin-bottom: 15px;
}
/* Botones de exportación */
section div {
  margin-bottom: 10px;
}
/* Errores */
ul {
  margin-top: 10px;
  padding-left: 20px;
}
li {
  color: #555;
  font-size: 14px;
}
/* Responsividad */
@media (max-width: 768px) {
  .cargar-ventas {
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
