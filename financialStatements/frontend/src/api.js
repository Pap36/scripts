import axios from "axios";

const api = axios.create({
  baseURL: "http://localhost:8000/api"
});

export async function fetchMetricsMonthly(params) {
  const { data } = await api.get("/metrics/monthly", { params });
  return data.items;
}

export async function fetchMetricsSummary(params) {
  const { data } = await api.get("/metrics/summary", { params });
  return data.totals;
}

export async function fetchTransactions(params) {
  const { data } = await api.get("/transactions", { params });
  return data;
}

export async function updateTransaction(id, payload) {
  const { data } = await api.patch(`/transactions/${id}`, payload);
  return data;
}

export async function uploadStatement(file) {
  const formData = new FormData();
  formData.append("file", file);
  const { data } = await api.post("/statements/upload", formData);
  return data;
}

export async function fetchStatements() {
  const { data } = await api.get("/statements");
  return data.items;
}

export async function updateStatement(id, payload) {
  const { data } = await api.patch(`/statements/${id}`, payload);
  return data;
}
