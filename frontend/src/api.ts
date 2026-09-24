export async function api<T>(
  path: string,
  body?: unknown,
  method?: string,
): Promise<T> {
  const response = await fetch(
    `/api${path}`,
    body === undefined && !method
      ? undefined
      : {
          method: method || "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        },
  );
  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ detail: "Backend no disponible" }));
    const detail = Array.isArray(error.detail)
      ? error.detail
          .map(
            (item: { loc?: string[]; msg: string }) =>
              `${item.loc?.slice(1).join(".")}: ${item.msg}`,
          )
          .join("; ")
      : error.detail;
    throw new Error(detail || "Error de conexión");
  }
  return response.json();
}
export function time(seconds = 0) {
  return new Date(Math.max(0, seconds) * 1000).toISOString().slice(11, 19);
}
