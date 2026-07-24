const API_BASE = import.meta.env.VITE_API_BASE || '';

export async function getHealth() {
  const response = await fetch(`${API_BASE}/health`);
  if (!response.ok) {
    throw new Error('health check failed');
  }
  return response.json();
}

