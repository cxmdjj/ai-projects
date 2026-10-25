const STORAGE_KEY = 'reason-analyze.latest-tasks.v1';

type TaskMap = Record<string, number>;

function readMap(): TaskMap {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return {};
    const parsed: unknown = JSON.parse(raw);
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return {};
    return parsed as TaskMap;
  } catch {
    return {};
  }
}

function writeMap(map: TaskMap): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(map));
  } catch {
    // localStorage 不可用时忽略，仅影响刷新后的结果恢复。
  }
}

export function rememberLatestTask(conversationId: number, taskId: number): void {
  const map = readMap();
  map[String(conversationId)] = taskId;
  writeMap(map);
}

export function getLatestTaskId(conversationId: number): number | null {
  const value = readMap()[String(conversationId)];
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

export function forgetLatestTask(conversationId: number): void {
  const map = readMap();
  delete map[String(conversationId)];
  writeMap(map);
}
