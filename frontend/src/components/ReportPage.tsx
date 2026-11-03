import React, { useState } from 'react';
import { useKeycloak } from '@react-keycloak/web';

// Shape of the Reports API response (GET /reports, format=json).
interface ReportRow {
  prosthesis_id: number;
  model: string;
  report_date: string;
  events_count: number;
  avg_response_ms: number;
  max_response_ms: number;
  p95_response_ms: number;
  errors_count: number;
  avg_battery_pct: number;
  movements_count: number;
  first_event_ts: string;
  last_event_ts: string;
}

interface ReportSummary {
  prostheses: number;
  days: number;
  total_events: number;
  total_errors: number;
  avg_response_ms: number;
}

interface ReportResponse {
  user_email: string;
  username: string | null;
  customer_id: number | null;
  name: string | null;
  region: string | null;
  generated_at: string;
  rows: ReportRow[];
  summary: ReportSummary;
}

// NOTE: the target architecture uses a BFF so the browser never holds tokens.
// For this assignment step the SPA calls the API directly with its Keycloak
// access token (obtained via Authorization Code + PKCE).
const API_BASE =
  process.env.REACT_APP_REPORTS_API_URL || process.env.REACT_APP_API_URL || '';

const ReportPage: React.FC = () => {
  const { keycloak, initialized } = useKeycloak();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [report, setReport] = useState<ReportResponse | null>(null);

  const fetchReport = async () => {
    try {
      setLoading(true);
      setError(null);
      setReport(null);

      // Refresh the token if it expires within 30s, then use it.
      await keycloak.updateToken(30).catch(() => undefined);
      if (!keycloak?.token) {
        setError('Вы не авторизованы. Войдите в систему.');
        return;
      }

      const response = await fetch(`${API_BASE}/reports`, {
        headers: { Authorization: `Bearer ${keycloak.token}` }
      });

      if (response.status === 401) {
        setError('Сессия истекла или токен недействителен (401). Войдите заново.');
        return;
      }
      if (response.status === 403) {
        setError('Недостаточно прав (403): требуется роль «prothetic_user».');
        return;
      }
      if (!response.ok) {
        setError(`Ошибка сервиса отчётов: HTTP ${response.status}.`);
        return;
      }

      const data: ReportResponse = await response.json();
      setReport(data);
    } catch (err) {
      setError(
        err instanceof Error
          ? `Сеть недоступна: ${err.message}`
          : 'Произошла непредвиденная ошибка.'
      );
    } finally {
      setLoading(false);
    }
  };

  const triggerDownload = (content: string, filename: string, type: string) => {
    const blob = new Blob([content], { type });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    link.click();
    URL.revokeObjectURL(url);
  };

  const downloadJson = () => {
    if (!report) return;
    triggerDownload(JSON.stringify(report, null, 2), 'report.json', 'application/json');
  };

  const downloadCsv = () => {
    if (!report) return;
    const columns: (keyof ReportRow)[] = [
      'prosthesis_id', 'model', 'report_date', 'events_count', 'avg_response_ms',
      'max_response_ms', 'p95_response_ms', 'errors_count', 'avg_battery_pct',
      'movements_count', 'first_event_ts', 'last_event_ts'
    ];
    const header = columns.join(',');
    const lines = report.rows.map((row) =>
      columns.map((col) => String(row[col])).join(',')
    );
    triggerDownload([header, ...lines].join('\n'), 'report.csv', 'text/csv');
  };

  if (!initialized) {
    return <div>Loading...</div>;
  }

  if (!keycloak.authenticated) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen bg-gray-100">
        <button
          onClick={() => keycloak.login()}
          className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
        >
          Login
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center min-h-screen bg-gray-100 py-10">
      <div className="p-8 bg-white rounded-lg shadow-md w-full max-w-5xl">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-2xl font-bold">Отчёт по протезу</h1>
          <button
            onClick={() => keycloak.logout()}
            className="px-3 py-1 text-sm text-gray-600 hover:text-gray-900"
          >
            Выйти
          </button>
        </div>

        <div className="flex flex-wrap gap-3 items-center">
          <button
            onClick={fetchReport}
            disabled={loading}
            className={`px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 ${
              loading ? 'opacity-50 cursor-not-allowed' : ''
            }`}
          >
            {loading ? 'Загрузка…' : 'Скачать отчёт'}
          </button>

          {report && report.rows.length > 0 && (
            <>
              <button
                onClick={downloadJson}
                className="px-4 py-2 bg-gray-200 text-gray-800 rounded hover:bg-gray-300"
              >
                JSON
              </button>
              <button
                onClick={downloadCsv}
                className="px-4 py-2 bg-gray-200 text-gray-800 rounded hover:bg-gray-300"
              >
                CSV
              </button>
            </>
          )}
        </div>

        {error && (
          <div className="mt-4 p-4 bg-red-100 text-red-700 rounded">{error}</div>
        )}

        {report && report.rows.length === 0 && (
          <div className="mt-4 p-4 bg-yellow-100 text-yellow-800 rounded">
            Данные по вашему протезу пока отсутствуют.
          </div>
        )}

        {report && report.rows.length > 0 && (
          <div className="mt-6">
            <div className="mb-4 text-sm text-gray-600">
              <div>
                Пользователь: <span className="font-medium">{report.name || report.user_email}</span>
                {report.region ? ` · ${report.region}` : ''}
              </div>
              <div>
                Протезов: {report.summary.prostheses} · Дней: {report.summary.days} ·
                Событий: {report.summary.total_events} · Ошибок: {report.summary.total_errors} ·
                Ср. отклик: {report.summary.avg_response_ms} мс
              </div>
            </div>

            <div className="overflow-x-auto">
              <table className="min-w-full text-sm border border-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-3 py-2 text-left">Дата</th>
                    <th className="px-3 py-2 text-left">Протез</th>
                    <th className="px-3 py-2 text-right">События</th>
                    <th className="px-3 py-2 text-right">Ср. отклик, мс</th>
                    <th className="px-3 py-2 text-right">p95, мс</th>
                    <th className="px-3 py-2 text-right">Макс, мс</th>
                    <th className="px-3 py-2 text-right">Ошибки</th>
                    <th className="px-3 py-2 text-right">Батарея, %</th>
                    <th className="px-3 py-2 text-right">Движения</th>
                  </tr>
                </thead>
                <tbody>
                  {report.rows.map((row, idx) => (
                    <tr key={`${row.prosthesis_id}-${row.report_date}-${idx}`} className="border-t">
                      <td className="px-3 py-2">{row.report_date}</td>
                      <td className="px-3 py-2">{row.model} (#{row.prosthesis_id})</td>
                      <td className="px-3 py-2 text-right">{row.events_count}</td>
                      <td className="px-3 py-2 text-right">{row.avg_response_ms.toFixed(1)}</td>
                      <td className="px-3 py-2 text-right">{row.p95_response_ms.toFixed(1)}</td>
                      <td className="px-3 py-2 text-right">{row.max_response_ms}</td>
                      <td className="px-3 py-2 text-right">{row.errors_count}</td>
                      <td className="px-3 py-2 text-right">{row.avg_battery_pct.toFixed(0)}</td>
                      <td className="px-3 py-2 text-right">{row.movements_count}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default ReportPage;
