```vue
<template>
  <div class="cargar-cantidades">
    <h1>Compra de Productos</h1>

    <section class="menu-buttons">
      <button @click="volverAlMenu" class="btn btn-secondary">Volver al Menú Principal</button>
      <button @click="limpiarPagina" class="btn btn-warning">Limpiar Página</button>
    </section>

    <!-- Subida de Archivo CSV -->
    <section>
      <h2>Subir Archivo</h2>
      <div>
        <label for="inputCsv">Archivo CSV:</label>
        <input id="inputCsv" type="file" @change="cargarCsv" class="form-control" :disabled="isLoading" />
      </div>
      <button @click="procesarCsv" :disabled="isLoading" class="btn btn-primary">
        {{ isLoading ? 'Procesando...' : 'Cargar Cantidades Productos' }}
      </button>
      <div v-if="isLoading" class="spinner">
        <div class="spinner-icon"></div>
        <p>Procesando archivo, por favor espera...</p>
      </div>
    </section>
    <section v-if="errores.length">
      <h2>Errores detectados:</h2>
      <ul>
        <li v-for="(error, index) in errores" :key="index">{{ error }}</li>
      </ul>
    </section>

    <!-- Descarga de Plantilla -->
    <section>
      <h2>Descargar Plantilla</h2>
      <button @click="descargarPlantilla" :disabled="isLoading">Descargar</button>
    </section>

    <!-- Consulta de Facturas -->
    <section class="consulta-facturas">
      <h2>Consulta de Facturas de Compra</h2>
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
        <label for="selectorFactura">Seleccionar Factura:</label>
        <select v-model="filtroFactura" id="selectorFactura" class="form-control" :disabled="isLoading">
          <option value="" disabled>Seleccione una factura</option>
          <option v-for="factura in facturas" :key="factura" :value="factura">{{ factura }}</option>
        </select>
      </div>
      <button @click="consultarFacturas" :disabled="isLoading">Consultar Facturas</button>
    </section>

    <!-- Resultados de la Consulta -->
    <section v-if="resultadosFacturas.length" class="resultados-facturas">
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
          <tr v-for="factura in resultadosFacturas" :key="factura.factura">
            <td>{{ factura.factura }}</td>
            <td>{{ factura.fecha }}</td>
            <td>
              <button @click="verDetalleFactura(factura.factura)" class="btn btn-info" :disabled="isLoading">Detalle</button>
            </td>
          </tr>
        </tbody>
      </table>
    </section>

    <!-- Detalle de la Factura -->
    <section v-if="detalleFactura.length" class="detalle-factura">
      <h3>Detalle de la Factura de Compra {{ facturaSeleccionada }}</h3>
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
            <th>Bodega</th>
            <th>Costo Unitario</th>
            <th>Costo Total</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in detalleFactura" :key="item.id">
            <td>{{ item.codigo }}</td>
            <td>{{ item.nombre }}</td>
            <td>{{ item.cantidad }}</td>
            <td>{{ item.bodega }}</td>
            <td>{{ item.costo_unitario ? `$${item.costo_unitario.toFixed(2)}` : 'N/A' }}</td>
            <td>{{ item.costo_total ? `$${item.costo_total.toFixed(2)}` : 'N/A' }}</td>
          </tr>
        </tbody>
      </table>
    </section>

    <!-- Mostrar errores -->
    <section v-if="errores.length">
      <h2>Errores detectados:</h2>
      <ul>
        <li v-for="(error, index) in errores" :key="index">{{ error }}</li>
      </ul>
    </section>
  </div>
</template>

<script>
import apiClient from "../services/axios";
import * as XLSX from "xlsx";

export default {
  name: "CargarCantidades",
  data() {
    return {
      archivoCsv: null,
      errores: [],
      filtroFactura: "",
      fechaInicio: "",
      fechaFin: "",
      facturas: [],
      resultadosFacturas: [],
      detalleFactura: [],
      facturaSeleccionada: "",
      isLoading: false,
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

      this.isLoading = true;
      this.errores = [];

      const formData = new FormData();
      formData.append("file", this.archivoCsv);

      try {
        const response = await apiClient.post("/api/cargar_cantidades", formData, {
          headers: {
            "Content-Type": "multipart/form-data",
          },
        });
        alert(response.data.message);
        this.cargarFacturas();
      } catch (error) {
        console.error("Error al cargar cantidades:", error);
        if (error.response && error.response.data.errors) {
          this.errores = error.response.data.errors;
        } else {
          alert("Ocurrió un error al cargar las cantidades");
        }
      } finally {
        this.isLoading = false;
      }
    },
    descargarPlantilla() {
      const csvData = [
        ["factura", "codigo", "nombre", "cantidad", "bodega", "contenedor", "fecha_ingreso", "costo_unitario"],
        ["FAC001", "GRA05299901000000", "R5 BULK PASTEL YELLOW", "100", "Bodega1", "CONT001", "2024-12-01 10:00:00", "50.00"],
        ["ABC123", "GRA05299909000000", "R5 BULK PASTEL LIGTH PINK", "150", "Bodega2", "CONT002", "2024-12-01 10:30:00", "45.00"],
      ];
      const csvContent =
        "data:text/csv;charset=utf-8," +
        csvData.map((e) => e.join(",")).join("\n");
      const encodedUri = encodeURI(csvContent);
      const link = document.createElement("a");
      link.setAttribute("href", encodedUri);
      link.setAttribute("download", "plantilla_cargue_cantidades.csv");
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
      this.resultadosFacturas = [];
      this.detalleFactura = [];
      this.facturaSeleccionada = "";
      this.isLoading = false;
    },
    async cargarFacturas() {
      try {
        const response = await apiClient.get("/api/facturas");
        this.facturas = response.data.facturas;
      } catch (error) {
        console.error("Error al cargar facturas:", error);
      }
    },
    async consultarFacturas() {
      try {
        const params = {
          factura: this.filtroFactura || undefined,
          fecha_inicio: this.fechaInicio || undefined,
          fecha_fin: this.fechaFin || undefined,
        };
        const response = await apiClient.get("/api/consultar_facturas", { params });
        console.log("Respuesta de /api/consultar_facturas:", response.data);
        this.resultadosFacturas = response.data;
        this.detalleFactura = [];
      } catch (error) {
        console.error("Error al consultar facturas:", error);
        alert("Ocurrió un error al consultar las facturas.");
      }
    },
    async verDetalleFactura(factura) {
      try {
        console.log("Factura enviada a /api/detalle_factura:", factura);
        this.facturaSeleccionada = factura;
        const response = await apiClient.get("/api/detalle_factura", {
          params: { factura: factura }
        });
        console.log("Respuesta de /api/detalle_factura:", response.data);
        this.detalleFactura = response.data;
      } catch (error) {
        console.error("Error al obtener detalle de la factura:", error);
        alert("No se pudo recuperar el detalle de la factura.");
      }
    },
    exportarListadoExcel() {
      if (!this.resultadosFacturas.length) {
        alert("No hay datos para exportar a Excel.");
        return;
      }

      const worksheetData = [
        ["Resultado de consulta de Factura de Compras Cargadas"],
        [`Número de Factura: ${this.filtroFactura || 'Todos'}`],
        [`Fecha Inicio: ${this.fechaInicio || 'No especificada'}`],
        [`Fecha Fin: ${this.fechaFin || 'No especificada'}`],
        [], // Línea en blanco
        ["Nombre de Factura", "Fecha y Hora"],
      ];

      this.resultadosFacturas.forEach((factura) => {
        worksheetData.push([
          factura.factura,
          factura.fecha,
        ]);
      });

      const worksheet = XLSX.utils.aoa_to_sheet(worksheetData);
      const workbook = XLSX.utils.book_new();
      XLSX.utils.book_append_sheet(workbook, worksheet, "Facturas");
      XLSX.writeFile(workbook, `facturas_compras_${new Date().toISOString().slice(0,10)}.xlsx`);
    },
    exportarDetalleExcel() {
      if (!this.detalleFactura.length) {
        alert("No hay datos para exportar a Excel.");
        return;
      }

      const fechaCargue = this.resultadosFacturas.find(f => f.factura === this.facturaSeleccionada)?.fecha || "Desconocida";

      const worksheetData = [
        [`Detalle Factura ${this.facturaSeleccionada}`],
        [`Fecha de Cargue: ${fechaCargue}`],
        [], // Línea en blanco
        ["Código", "Nombre", "Cantidad", "Bodega", "Costo Unitario", "Costo Total"],
      ];

      this.detalleFactura.forEach((item) => {
        worksheetData.push([
          item.codigo,
          item.nombre,
          item.cantidad,
          item.bodega,
          item.costo_unitario || "N/A",
          item.costo_total || "N/A",
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
  },
};
</script>

<style scoped>
/* Contenedor principal */
.cargar-cantidades {
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
/* Spinner */
.spinner {
  display: flex;
  align-items: center;
  margin-top: 10px;
}
.spinner-icon {
  border: 4px solid #f3f3f3;
  border-top: 4px solid #007bff;
  border-radius: 50%;
  width: 24px;
  height: 24px;
  animation: spin 1s linear infinite;
  margin-right: 10px;
}
@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}
.spinner p {
  margin: 0;
  color: #555;
  font-size: 14px;
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
button:disabled {
  background-color: #6c757d;
  cursor: not-allowed;
}
button:hover:not(:disabled) {
  background-color: #0056b3;
  transform: translateY(-2px);
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.15);
}
.btn-secondary {
  background-color: #007bff;
}
.btn-secondary:hover:not(:disabled) {
  background-color: #0056b3;
}
.btn-warning {
  background-color: #ffc107;
  color: #333;
}
.btn-warning:hover:not(:disabled) {
  background-color: #e0a800;
}
.btn-info {
  background-color: #007bff;
}
.btn-info:hover:not(:disabled) {
  background-color: #0056b3;
}
.btn-primary {
  background-color: #007bff;
}
.btn-primary:hover:not(:disabled) {
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
input:disabled, select:disabled {
  background-color: #e9ecef;
  cursor: not-allowed;
}
input:focus, select:focus {
  border-color: #007bff;
  outline: none;
  box-shadow: 0 0 4px rgba(0, 123, 255, 0.25);
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
  .cargar-cantidades {
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
