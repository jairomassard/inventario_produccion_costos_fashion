<template>
  <div class="cargar-notas-credito">
    <h1>Cargar Notas Crédito</h1>

    <section class="menu-buttons">
      <button @click="volverAlMenu" class="btn btn-secondary">Volver al Menú Principal</button>
      <button @click="limpiarPagina" class="btn btn-warning">Limpiar Página</button>
    </section>

    <!-- Subida de Archivo CSV -->
    <section>
      <h2>Subir Archivo</h2>
      <div>
        <label for="inputCsv">Archivo CSV:</label>
        <input id="inputCsv" type="file" @change="cargarCsv" class="form-control" />
      </div>
      <p>El CSV debe incluir: nota_credito, factura de venta, codigo, nombre, cantidad, fecha_devolucion</p>
      <button @click="procesarCsv">Cargar Notas Crédito</button>
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
      <button @click="descargarPlantilla">Descargar</button>
    </section>

    <!-- Consulta de Notas Crédito -->
    <section class="consulta-notas-credito">
      <h2>Consulta de Notas Crédito</h2>
      <div>
        <label for="filtroNotaCredito">Número de Nota Crédito:</label>
        <input
          v-model="filtroNotaCredito"
          id="filtroNotaCredito"
          placeholder="Ingrese número de nota crédito"
          class="form-control"
        />
      </div>
      <div>
        <label for="fechaInicio">Fecha Inicio:</label>
        <input type="date" v-model="fechaInicio" id="fechaInicio" class="form-control" />
      </div>
      <div>
        <label for="fechaFin">Fecha Fin:</label>
        <input type="date" v-model="fechaFin" id="fechaFin" class="form-control" />
      </div>
      <div>
        <label for="selectorNotaCredito">Seleccionar Nota Crédito:</label>
        <select v-model="filtroNotaCredito" id="selectorNotaCredito" class="form-control">
          <option value="" disabled>Seleccione una nota crédito</option>
          <option v-for="nota in notasCredito" :key="nota" :value="nota">{{ nota }}</option>
        </select>
      </div>
      <button @click="consultarNotasCredito">Consultar Notas Crédito</button>
    </section>

    <!-- Resultados de la Consulta -->
    <section v-if="resultadosNotasCredito.length" class="resultados-notas-credito">
      <h3>Resultados de la Consulta</h3>
      <div>
        <button @click="exportarListadoExcel" class="btn btn-primary">Exportar Listado <i class="fas fa-file-excel excel-icon"></i></button>
      </div>
      <table>
        <thead>
          <tr>
            <th>Número de Nota Crédito</th>
            <th>Fecha y Hora</th>
            <th>Acción</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="nota in resultadosNotasCredito" :key="nota.nota_credito">
            <td>{{ nota.nota_credito }}</td>
            <td>{{ nota.fecha }}</td>
            <td>
              <button @click="verDetalleNotaCredito(nota.nota_credito)" class="btn btn-info">Detalle</button>
            </td>
          </tr>
        </tbody>
      </table>
    </section>

    <!-- Detalle de la Nota Crédito -->
    <section v-if="detalleNotaCredito.length" class="detalle-nota-credito">
      <h3>Detalle de la Nota Crédito {{ notaCreditoSeleccionada }}</h3>
      <div>
        <button @click="exportarDetalleExcel" class="btn btn-primary">Exportar <i class="fas fa-file-excel excel-icon"></i></button>
      </div>
      <table>
        <thead>
          <tr>
            <th>Código</th>
            <th>Nombre</th>
            <th>Cantidad Devuelta</th>
            <th>Bodega</th>
            <th>Costo Unitario</th>
            <th>Costo Total</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in detalleNotaCredito" :key="item.id">
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
  name: "CargarNotasCredito",
  data() {
    return {
      archivoCsv: null,
      errores: [],
      filtroNotaCredito: "",
      fechaInicio: "",
      fechaFin: "",
      notasCredito: [],
      resultadosNotasCredito: [],
      detalleNotaCredito: [],
      notaCreditoSeleccionada: "",
    };
  },
  methods: {
    cargarCsv(event) {
      this.archivoCsv = event.target.files[0];
    },
    cargarCsv(event) {
      this.archivoCsv = event.target.files[0];
    },
    async procesarCsv() {
      if (!this.archivoCsv) {
        alert("Seleccione un archivo para cargar");
        return;
      }

      const formData = new FormData();
      formData.append("file", this.archivoCsv);

      try {
        const response = await apiClient.post("/api/cargar_notas_credito", formData, {
          headers: {
            "Content-Type": "multipart/form-data",
          },
        });
        alert(response.data.message);
        this.errores = [];
        this.cargarNotasCredito();
      } catch (error) {
        console.error("Error al cargar notas crédito:", error);
        if (error.response && error.response.data.errors) {
          this.errores = error.response.data.errors;
        } else {
          alert("Ocurrió un error al cargar las notas crédito");
        }
      }
    },
    descargarPlantilla() {
      const csvData = [
        ["nota_credito", "factura", "codigo", "nombre", "cantidad", "fecha_devolucion"],
        ["NC001", "FB1234567", "GCP01333330000000", "Producto compuesto prueba", "2", "2025-04-08 17:00:00"],
        ["NC002", "CC9876543", "GRA05299909000000", "R5 BULK PASTEL LIGTH PINK", "75", "2025-04-09 10:30:00"],
      ];
      const csvContent =
        "data:text/csv;charset=utf-8," +
        csvData.map((e) => e.join(",")).join("\n");
      const encodedUri = encodeURI(csvContent);
      const link = document.createElement("a");
      link.setAttribute("href", encodedUri);
      link.setAttribute("download", "plantilla_cargue_notas_credito.csv");
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
      this.filtroNotaCredito = "";
      this.fechaInicio = "";
      this.fechaFin = "";
      this.resultadosNotasCredito = [];
      this.detalleNotaCredito = [];
      this.notaCreditoSeleccionada = "";
    },
    async cargarNotasCredito() {
      try {
        const response = await apiClient.get("/api/notas_credito");
        this.notasCredito = response.data.notas_credito;
      } catch (error) {
        console.error("Error al cargar notas crédito:", error);
      }
    },
    async consultarNotasCredito() {
      try {
        const params = {
          nota_credito: this.filtroNotaCredito || undefined,
          fecha_inicio: this.fechaInicio || undefined,
          fecha_fin: this.fechaFin || undefined,
        };
        const response = await apiClient.get("/api/consultar_notas_credito", { params });
        this.resultadosNotasCredito = response.data;
        this.detalleNotaCredito = [];
      } catch (error) {
        console.error("Error al consultar notas crédito:", error);
        alert("Ocurrió un error al consultar las notas crédito.");
      }
    },
    async verDetalleNotaCredito(notaCredito) {
      try {
        this.notaCreditoSeleccionada = notaCredito;
        const response = await apiClient.get("/api/detalle_nota_credito", {
          params: { nota_credito: notaCredito }
        });
        this.detalleNotaCredito = response.data;
      } catch (error) {
        console.error("Error al obtener detalle de la nota crédito:", error);
        alert("No se pudo recuperar el detalle de la nota crédito.");
      }
    },
    exportarListadoExcel() {
      if (!this.resultadosNotasCredito.length) {
        alert("No hay datos para exportar a Excel.");
        return;
      }

      const worksheetData = [
        ["Resultado de consulta de Notas Crédito Cargadas"],
        [`Número de Nota Crédito: ${this.filtroNotaCredito || 'Todas'}`],
        [`Fecha Inicio: ${this.fechaInicio || 'No especificada'}`],
        [`Fecha Fin: ${this.fechaFin || 'No especificada'}`],
        [], // Línea en blanco
        ["Nombre de Nota Crédito", "Fecha y Hora"],
      ];

      this.resultadosNotasCredito.forEach((nota) => {
        worksheetData.push([
          nota.nota_credito,
          nota.fecha,
        ]);
      });

      const worksheet = XLSX.utils.aoa_to_sheet(worksheetData);
      const workbook = XLSX.utils.book_new();
      XLSX.utils.book_append_sheet(workbook, worksheet, "Notas Crédito");
      XLSX.writeFile(workbook, `notas_credito_${new Date().toISOString().slice(0,10)}.xlsx`);
    },
    exportarDetalleExcel() {
      if (!this.detalleNotaCredito.length) {
        alert("No hay datos para exportar a Excel.");
        return;
      }

      const fechaCargue = this.resultadosNotasCredito.find(n => n.nota_credito === this.notaCreditoSeleccionada)?.fecha || "Desconocida";

      const worksheetData = [
        [`Detalle Nota Crédito ${this.notaCreditoSeleccionada}`],
        [`Fecha de Cargue: ${fechaCargue}`],
        [], // Línea en blanco
        ["Código", "Nombre", "Cantidad Devuelta", "Bodega", "Costo Unitario", "Costo Total"],
      ];

      this.detalleNotaCredito.forEach((item) => {
        worksheetData.push([
          item.codigo,
          item.nombre,
          item.cantidad,
          item.bodega,
          item.costo_unitario ? item.costo_unitario.toFixed(2) : "N/A",
          item.costo_total ? item.costo_total.toFixed(2) : "N/A",
        ]);
      });

      const worksheet = XLSX.utils.aoa_to_sheet(worksheetData);
      const workbook = XLSX.utils.book_new();
      XLSX.utils.book_append_sheet(workbook, worksheet, "Detalle Nota Crédito");
      XLSX.writeFile(workbook, `detalle_nota_credito_${this.notaCreditoSeleccionada}.xlsx`);
    },
  },
  mounted() {
    this.cargarNotasCredito();
  },
};
</script>

<style scoped>
/* Contenedor principal */
.cargar-notas-credito {
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
  background-color:  #007bff; /* Gris para "Volver al Menú" */
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
  .cargar-notas-credito {
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