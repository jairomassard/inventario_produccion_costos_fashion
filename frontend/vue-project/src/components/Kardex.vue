<template>
  <div class="kardex-view">
    <h1>Kardex de Inventario de Productos</h1>

    <!-- Botones de acción -->
    <div class="actions">
      <button @click="volverAlMenu" class="btn btn-secondary">Volver al Menú Principal</button>
      <button @click="limpiarPagina" class="btn btn-warning">Limpiar Página</button>
    </div>

    <!-- Filtros de búsqueda -->
    <section class="filters">
      <h2>Filtrar Movimientos</h2>
      <div class="filters-header">
        <label for="fechaInicio">Fecha inicio:</label>
        <input type="date" id="fechaInicio" v-model="fechaInicio" />

        <label for="fechaFin">Fecha fin:</label>
        <input type="date" id="fechaFin" v-model="fechaFin" />

        <button @click="consultarKardex" class="btn btn-primary">Consultar Kardex</button>
      </div>

      <div class="filters-products">
        <label for="nombreProducto">Buscar por nombre:</label>
        <input 
          type="text" 
          id="nombreProducto"
          v-model="nombreProducto"
          placeholder="Ingrese nombre del producto"
          class="form-control"
          @input="sincronizarPorNombre"
        />
      </div>
      <div class="filters-products">
        <label for="productoSelector">Seleccione un producto:</label>
        <select v-model="codigoProducto" id="productoSelector" @change="sincronizarSelectorConCodigo">
          <option value="" disabled>Seleccione un producto</option>
          <option v-for="producto in productos" :key="producto.codigo" :value="producto.codigo">
            {{ producto.codigo }} - {{ producto.nombre }}
          </option>
        </select>
      </div>
      <div class="filters-products">
        <label for="codigoProducto">O ingrese el código del producto:</label>
        <input
          type="text"
          id="codigoProducto"
          v-model="codigoProducto"
          placeholder="Ingrese el código del producto"
          class="form-control"
          @input="sincronizarCodigoConSelector"
        />
      </div>
    </section>

    <!-- Mensaje informativo -->
    <p class="info-message">
      Nota: Para incluir movimientos del día actual, seleccione un día adicional como fecha final.
    </p>

    <!-- Tabla de resumen -->
    <section v-if="kardex.length" class="summary">
      <h2>Resumen por Almacén</h2>
      <div class="cpp-global">
        <span>CPP GLOBAL</span>
        <span>{{ cppGlobal ? `$${cppGlobal.toFixed(2)}` : 'N/A' }}</span>
      </div>
      <div class="table-responsive">
        <table>
          <thead>
            <tr>
              <th>ALMACÉN</th>
              <th>STOCK FINAL</th>
              <th>VALOR ACUMULADO</th>
              <th>CPP</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(resumen, index) in resumenPorAlmacen" :key="index">
              <td>{{ resumen.almacen }}</td>
              <td>{{ resumen.stockFinal }}</td>
              <td>{{ resumen.valorAcumulado ? `$${resumen.valorAcumulado.toFixed(2)}` : 'N/A' }}</td>
              <td>{{ resumen.cpp ? `$${resumen.cpp.toFixed(2)}` : 'N/A' }}</td>
            </tr>
            <tr class="total-row">
              <td><strong>TOTAL</strong></td>
              <td><strong>{{ totalStock }}</strong></td>
              <td><strong>{{ totalValor ? `$${totalValor.toFixed(2)}` : 'N/A' }}</strong></td>
              <td></td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>


    <!-- Filtro por bodega -->
    <section v-if="kardex.length" class="filters-bodega">
      <h3>Filtrar por Almacén</h3>
      <div class="bodega-checkboxes">
        <label class="checkbox-container">
          <input 
            type="checkbox" 
            value="" 
            v-model="bodegasSeleccionadas" 
            @change="filtrarPorBodega"
          >
          <span>Todos</span>
        </label>
        <label v-for="bodega in bodegas" :key="bodega.id" class="checkbox-container">
          <input 
            type="checkbox" 
            :value="bodega.nombre" 
            v-model="bodegasSeleccionadas" 
            @change="filtrarPorBodega"
          >
          <span>{{ bodega.nombre }}</span>
        </label>
      </div>
    </section>

    <!-- Tabla de resultados -->
    <section v-if="kardexFiltrado.length" class="results">
      <h2>Movimientos del Producto</h2>
      <div>
        <button @click="imprimirKardexPDF" class="btn btn-success" title="Imprimir PDF"><i class="fas fa-file-pdf pdf-icon"></i></button>
        <button @click="exportarKardexCSV" class="btn btn-info" title="Exportar CSV"><i class="fa-light fa-file-csv csv-icon"></i></button>
        <button @click="exportarKardexExcel" class="btn btn-primary" title="Exportar Excel"><i class="fas fa-file-excel excel-icon"></i></button>
      </div>
      <div class="table-responsive">
        <!-- eQUIVALENCIAS EN TABLA -->
         <!-- FECHA = FECHA -->
         <!-- TIPO = DOCUMENTO-->
         <!-- CANTIDAD = CANTIDAD --> 
         <!-- BODEGA = ALMACEN -->
         <!-- COSTO UNITARIO = COSTO -->  
         <!-- COSTO TOTAL = COSTO TOTAL -->  
         <!-- SALDO = CANTIDAD ACUMULADA-->  
         <!-- Saldo Costo Unitario Bodega = CPP -->
         <!-- Saldo Costo Total Bodega = VALOR ACUMULADO --> 
         <!-- Saldo Costo Unitario Global = CPP GLOBAL -->  
         <!-- DESCRIPCION = DESCRIPCION -->  
        <table>
          <thead>
            <tr>
              <th>Fecha</th>
              <th>Documento</th>
              <th>Almacén</th>
              <th>Cant.</th>
              <th>Costo</th>
              <th>Costo Total</th>
              <th>Cantidad Acumulada</th>
              <th>Valor Acumulado</th>
              <th>CPP</th> 
              <th>CPP Global</th> <!-- Nueva columna -->
              <th>Descripción</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(registro, index) in kardexFiltrado" :key="index">
              <td>{{ registro.fecha }}</td>
              <td>{{ registro.tipo }}</td>
              <td>{{ registro.bodega || 'N/A' }}</td>
              <td>{{ registro.tipo === 'SALIDA' ? `-${registro.cantidad}` : registro.cantidad }}</td>
              <td>{{ registro.costo_unitario ? `$${registro.costo_unitario.toFixed(2)}` : 'N/A' }}</td>
              <!--<td>{{ registro.costo_total === 'SALIDA' ? `-$${registro.costo_total.toFixed(2)}` : `$${registro.costo_total.toFixed(2)}` }}</td>-->
              <td>{{ registro.tipo === 'SALIDA' ? `-$${registro.costo_total.toFixed(2)}` : `$${registro.costo_total.toFixed(2)}` }}</td>
              <td>{{ registro.saldo }}</td>
              <td>{{ registro.saldo_costo_total !== null && registro.saldo_costo_total !== undefined ? `$${registro.saldo_costo_total.toFixed(2)}` : 'N/A' }}</td>
              <td>{{ registro.saldo_costo_unitario ? `$${registro.saldo_costo_unitario.toFixed(2)}` : 'N/A' }}</td>
              <td>{{ registro.saldo_costo_unitario_global ? `$${registro.saldo_costo_unitario_global.toFixed(2)}` : 'N/A' }}</td>
              <td>{{ registro.descripcion }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <button @click="imprimirKardexPDF" class="btn btn-success" title="Imprimir PDF"><i class="fas fa-file-pdf pdf-icon"></i></button>
      <button @click="exportarKardexCSV" class="btn btn-info" title="Exportar CSV"><i class="fa-light fa-file-csv csv-icon"></i></button>
      <button @click="exportarKardexExcel" class="btn btn-primary" title="Exportar Excel"><i class="fas fa-file-excel excel-icon"></i></button>
    </section>

    <!-- Sin resultados -->
    <section v-else>
      <p>No hay datos para mostrar. Realice una consulta o ajuste el filtro por bodega.</p>
    </section>
  </div>
</template>

<script>
import apiClient from "../services/axios";
import * as XLSX from "xlsx";

export default {
  name: "KardexView",
  data() {
    return {
      productos: [],
      bodegas: [],
      codigoProducto: "",
      nombreProducto: "",
      fechaInicio: "",
      fechaFin: "",
      kardex: [],
      kardexFiltrado: [],
      bodegasSeleccionadas: [], // Cambiado de bodegaSeleccionada a array
      resumenPorAlmacen: [], // Nueva propiedad para el resumen
      cppGlobal: null, // Nueva propiedad para CPP Global
      totalStock: 0, // Nueva propiedad
      totalValor: 0, // Nueva propiedad
    };
  },
  methods: {
    limpiarPagina() {
      this.codigoProducto = "";
      this.nombreProducto = "";
      this.fechaInicio = "";
      this.fechaFin = "";
      this.kardex = [];
      this.kardexFiltrado = [];
      this.bodegasSeleccionadas = []; // Limpiar selección
    },
    async cargarProductos() {
      try {
        const response = await apiClient.get("/api/productos/completos");
        this.productos = response.data
          .sort((a, b) => a.codigo.localeCompare(b.codigo))
          .map(producto => ({
            codigo: producto.codigo,
            nombre: producto.nombre
          }));
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
        console.error("Error al cargar las bodegas:", error);
        alert("No se pudieron cargar las bodegas.");
      }
    },
    async consultarKardex() {
      if (!this.codigoProducto || !this.fechaInicio || !this.fechaFin) {
          alert("Debe seleccionar un producto y definir un rango de fechas.");
          return;
      }

      try {
          const params = {
              codigo: this.codigoProducto,
              fecha_inicio: this.fechaInicio,
              fecha_fin: this.fechaFin,
          };
          if (this.bodegasSeleccionadas.length > 0 && !this.bodegasSeleccionadas.includes("")) {
              params.bodegas = this.bodegasSeleccionadas.join(",");
          }

          const response = await apiClient.get("/api/kardex", { params });

          this.kardex = response.data.kardex;
          this.kardexFiltrado = [...this.kardex];
          this.calcularResumen();
      } catch (error) {
          console.error("Error al consultar el kardex:", error);
          alert("No se pudo consultar el kardex.");
      }
    },
    calcularResumen() {
      const almacenes = [...new Set(this.kardex.map(mov => mov.bodega))];
      this.resumenPorAlmacen = almacenes.map(almacen => {
        const movimientosAlmacen = this.kardex
          .filter(mov => mov.bodega === almacen)
          .sort((a, b) => new Date(b.fecha) - new Date(a.fecha));
        const ultimoMovimiento = movimientosAlmacen[0];
        return {
          almacen,
          stockFinal: ultimoMovimiento.saldo,
          valorAcumulado: ultimoMovimiento.saldo_costo_total,
          cpp: ultimoMovimiento.saldo_costo_unitario,
        };
      }).sort((a, b) => a.almacen.localeCompare(b.almacen));

      this.totalStock = this.resumenPorAlmacen.reduce((sum, r) => sum + r.stockFinal, 0);
      this.totalValor = this.resumenPorAlmacen.reduce((sum, r) => sum + (r.valorAcumulado || 0), 0);
      this.cppGlobal = this.totalStock > 0 ? this.totalValor / this.totalStock : 0;
    },
    filtrarPorBodega() {
      if (this.bodegasSeleccionadas.includes("")) {
        // Si "Todos" está seleccionado, mostrar todo
        this.kardexFiltrado = [...this.kardex];
      } else if (this.bodegasSeleccionadas.length === 0) {
        // Si no hay selección, mostrar todo por defecto
        this.kardexFiltrado = [...this.kardex];
      } else {
        // Filtrar por las bodegas seleccionadas
        this.kardexFiltrado = this.kardex.filter(mov =>
          this.bodegasSeleccionadas.includes(mov.bodega)
        );
      }
    },
    async imprimirKardexPDF() {
      if (!this.codigoProducto || !this.fechaInicio || !this.fechaFin) {
        alert("Debe realizar una consulta antes de generar el PDF.");
        return;
      }
      try {
        const params = {
          codigo: this.codigoProducto,
          fecha_inicio: this.fechaInicio,
          fecha_fin: this.fechaFin,
        };
        if (this.bodegasSeleccionadas.length > 0 && !this.bodegasSeleccionadas.includes("")) {
          params.bodegas = this.bodegasSeleccionadas.join(",");
        }
        const response = await apiClient.get("/api/kardex/pdf", {
          params,
          responseType: "blob",
        });
        const url = window.URL.createObjectURL(new Blob([response.data]));
        const link = document.createElement("a");
        link.href = url;
        link.setAttribute("download", `kardex_${this.codigoProducto}${this.bodegasSeleccionadas.length ? '_' + this.bodegasSeleccionadas.join('_') : ''}.pdf`);
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
      } catch (error) {
        console.error("Error al generar el PDF del Kardex:", error);
        alert("No se pudo generar el PDF del Kardex. Por favor, intenta de nuevo o contacta al soporte.");
      }
    },
    exportarKardexCSV() {
      if (!this.kardexFiltrado.length) {
        alert("No hay datos filtrados para exportar a CSV.");
        return;
      }
      let csvContent =
        "data:text/csv;charset=utf-8," +
        `Kardex de Inventario\n` +
        `Producto: ${this.codigoProducto} - ${this.productos.find((p) => p.codigo === this.codigoProducto)?.nombre || "Desconocido"}\n` +
        `Rango de Fechas: ${this.fechaInicio} a ${this.fechaFin}\n` +
        `Bodega: ${this.bodegasSeleccionadas.length > 0 && !this.bodegasSeleccionadas.includes("") ? this.bodegasSeleccionadas.join(", ") : "Todas"}\n\n` +
        `Resumen por Almacén\n` +
        `CPP GLOBAL;${this.cppGlobal ? this.cppGlobal.toFixed(2) : "N/A"}\n\n` +
        `ALMACÉN;STOCK FINAL;VALOR ACUMULADO;CPP\n` +
        this.resumenPorAlmacen.map(resumen =>
          `${resumen.almacen};${resumen.stockFinal};${resumen.valorAcumulado ? resumen.valorAcumulado.toFixed(2) : "N/A"};${resumen.cpp ? resumen.cpp.toFixed(2) : "N/A"}`
        ).join("\n") + "\n" +
        `TOTAL;${this.totalStock};${this.totalValor ? this.totalValor.toFixed(2) : "N/A"};\n\n` +
        `Movimientos del Producto\n` +
        `Fecha;Documento;Almacén;Cant.;Costo;Costo Total;Cantidad Acumulada;Valor Acumulado;CPP;CPP Global;Descripción\n` +
        this.kardexFiltrado.map(mov => [
          mov.fecha,
          mov.tipo,
          mov.bodega || "N/A",
          mov.tipo === "SALIDA" ? -mov.cantidad : mov.cantidad,
          mov.costo_unitario ? mov.costo_unitario.toFixed(2) : "N/A",
          mov.tipo === "SALIDA" ? -mov.costo_total : mov.costo_total ? mov.costo_total.toFixed(2) : "N/A",
          mov.saldo,
          mov.saldo_costo_total !== undefined && mov.saldo_costo_total !== null ? mov.saldo_costo_total.toFixed(2) : "N/A",
          mov.saldo_costo_unitario ? mov.saldo_costo_unitario.toFixed(2) : "N/A",
          mov.saldo_costo_unitario_global ? mov.saldo_costo_unitario_global.toFixed(2) : "N/A",
          mov.descripcion.replace(/;/g, " "),
        ].join(";")).join("\n");
      const encodedUri = encodeURI(csvContent);
      const link = document.createElement("a");
      link.setAttribute("href", encodedUri);
      link.setAttribute("download", `kardex_${this.codigoProducto}${this.bodegasSeleccionadas.length ? '_' + this.bodegasSeleccionadas.join('_') : ''}.csv`);
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    },
    exportarKardexExcel() {
      if (!this.kardexFiltrado.length) {
        alert("No hay datos filtrados para exportar a Excel.");
        return;
      }
      const worksheetData = [
        ["Kardex de Inventario"],
        [`Producto: ${this.codigoProducto} - ${this.productos.find((p) => p.codigo === this.codigoProducto)?.nombre || "Desconocido"}`],
        [`Rango de Fechas: ${this.fechaInicio} a ${this.fechaFin}`],
        [`Bodega: ${this.bodegasSeleccionadas.length > 0 && !this.bodegasSeleccionadas.includes("") ? this.bodegasSeleccionadas.join(", ") : "Todas"}`],
        [],
        ["Resumen por Almacén"],
        ["CPP GLOBAL", this.cppGlobal ? this.cppGlobal.toFixed(2) : "N/A"],
        [],
        ["ALMACÉN", "STOCK FINAL", "VALOR ACUMULADO", "CPP"],
        ...this.resumenPorAlmacen.map(resumen => [
          resumen.almacen,
          resumen.stockFinal,
          resumen.valorAcumulado ? resumen.valorAcumulado.toFixed(2) : "N/A",
          resumen.cpp ? resumen.cpp.toFixed(2) : "N/A",
        ]),
        ["TOTAL", this.totalStock, this.totalValor ? this.totalValor.toFixed(2) : "N/A", ""],
        [],
        ["Movimientos del Producto"],
        ["Fecha", "Documento", "Almacén", "Cant.", "Costo", "Costo Total", "Cant. Acumulada", "Valor Acumulado", "CPP", "CPP Global", "Descripción"],
        ...this.kardexFiltrado.map(mov => [
          mov.fecha,
          mov.tipo,
          mov.bodega || "N/A",
          mov.tipo === "SALIDA" ? -mov.cantidad : mov.cantidad,
          mov.costo_unitario ? mov.costo_unitario.toFixed(2) : "N/A",
          mov.tipo === "SALIDA" ? -mov.costo_total : mov.costo_total ? mov.costo_total.toFixed(2) : "N/A",
          mov.saldo,
          mov.saldo_costo_total !== undefined && mov.saldo_costo_total !== null ? mov.saldo_costo_total.toFixed(2) : "N/A",
          mov.saldo_costo_unitario ? mov.saldo_costo_unitario.toFixed(2) : "N/A",
          mov.saldo_costo_unitario_global ? mov.saldo_costo_unitario_global.toFixed(2) : "N/A",
          mov.descripcion,
        ]),
      ];
      const worksheet = XLSX.utils.aoa_to_sheet(worksheetData);
      const workbook = XLSX.utils.book_new();
      XLSX.utils.book_append_sheet(workbook, worksheet, "Kardex");
      XLSX.writeFile(workbook, `kardex_${this.codigoProducto}${this.bodegasSeleccionadas.length ? '_' + this.bodegasSeleccionadas.join('_') : ''}.xlsx`);
    },

    sincronizarPorNombre() {
      const productoEncontrado = this.productos.find((p) => 
        p.nombre.toLowerCase().includes(this.nombreProducto.toLowerCase())
      );
      if (productoEncontrado) {
        this.codigoProducto = productoEncontrado.codigo;
      }
    },
    sincronizarCodigoConSelector() {
      const productoEncontrado = this.productos.find(p => p.codigo === this.codigoProducto);
      if (productoEncontrado) {
        this.nombreProducto = productoEncontrado.nombre;
      }
    },
    sincronizarSelectorConCodigo() {
      const productoEncontrado = this.productos.find(p => p.codigo === this.codigoProducto);
      if (productoEncontrado) {
        this.nombreProducto = productoEncontrado.nombre;
      }
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
  },
  mounted() {
    this.cargarProductos();
    this.cargarBodegas();
  },
};
</script>

 
  <style scoped>
  .kardex-view {
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
  .pdf-icon {
    font-size: 18px;
    vertical-align: middle;
    margin-left: 5px;
    color: #fff;
  }
  .csv-icon {
    font-size: 18px;
    vertical-align: middle;
    margin-left: 5px;
    color: #fff;
  }
  h1 {
    text-align: center;
    margin-bottom: 20px;
  }
  
  .actions {
    display: flex;
    justify-content: space-between;
    margin-bottom: 20px;
  }
  
  .filters {
    padding: 15px;
    border: 1px solid #e9ecef;
    border-radius: 6px;
    background-color: #f8f9fa;
    margin-bottom: 20px;
  }
  
  .filters-header {
    display: flex;
    gap: 1rem;
    flex-wrap: wrap;
  }
  
  .filters-products {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }
  
  .filters label {
    font-weight: bold;
  }
  
  input,
  select {
    padding: 10px;
    border: 1px solid #ccc;
    border-radius: 4px;
    font-size: 14px;
    margin-bottom: 10px;
  }
  
  .info-message {
    margin-top: 10px;
    font-style: italic;
    color: #555;
  }
  
  .results {
    margin-top: 20px;
  }
  
  .table-responsive {
    overflow-x: auto;
  }
  
  table {
    width: 100%;
    border-collapse: collapse;
  }
  
  th,
  td {
    border: 1px solid #ddd;
    padding: 10px;
    text-align: left;
  }
  
  th {
    background-color: #f8f9fa;
  }
  
  tbody tr:hover {
    background-color: #f1f1f1;
  }
  
  button {
    padding: 0.5rem 1rem;
    border: none;
    background-color: #007bff;
    color: #fff;
    cursor: pointer;
    border-radius: 4px;
  }
  
  button:hover {
    background-color: #0056b3;
  }

  button.btn-warning {
    background-color: #ffc107; /* Amarillo para advertencias */
    color: #333; /* Texto oscuro */
  }
  
  button.btn-warning:hover {
    background-color: #e0a800; /* Amarillo más oscuro */
  }
  
  /* Responsivo */
  @media (max-width: 768px) {
    .filters-header {
      flex-direction: column;
    }
  
    table {
      display: block;
      overflow-x: auto;
      white-space: nowrap;
    }
  }

  .summary {
    margin-top: 20px;
  }

  .summary table {
    width: 60%;
    margin-bottom: 20px;
  }

  .summary th,
  .summary td {
    border: 1px solid #ddd;
    padding: 10px;
    text-align: left;
  }

  .summary th {
    background-color: #e9ecef;
  }
  
  .cpp-global {
  margin-bottom: 10px;
  font-size: 16px;
  font-weight: bold;
  display: flex;
  justify-content: space-between;
  width: 200px;
  }

  .total-row td {
    font-weight: bold;
  }

  .filters-bodega {
    padding: 15px;
    border: 1px solid #e9ecef;
    border-radius: 6px;
    background-color: #f8f9fa;
    margin-top: 20px;
  }

  .filters-bodega h3 {
    margin: 0 0 10px 0;
    font-size: 18px;
  }

  .bodega-checkboxes {
    display: flex;
    flex-wrap: wrap;
    gap: 20px;
    padding: 10px 0;
  }

  .checkbox-container {
    display: flex;
    align-items: center;
    gap: 5px;
  }

  .checkbox-container input[type="checkbox"] {
    margin: 0;
    accent-color: #007bff;
  }

  .checkbox-container span {
    font-size: 14px;
    color: #333;
  }

  .checkbox-container:hover span {
    color: #007bff;
  }

  </style>